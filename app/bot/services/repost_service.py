from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, MessageEntity

from app.bot.services.language_service import t
from app.bot.services.link_service import (
    channel_link_from_pair_channel,
    post_link,
    strip_visible_links_with_entities,
)
from app.bot.services.pair_service import build_route
from app.db.models import LoopEvent, Pair, PairChannel, PostItem, PostUnit
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
FOOTER_EDIT_DELAY_SECONDS = 15
MAX_SEND_ATTEMPTS = 3
MAX_EDIT_ATTEMPTS = 3
EMPTY_TEXT_PLACEHOLDER = '\u2063'

# Closes the small race between Telegram returning a created message and the DB commit
# becoming visible to the channel_post handler. Entries expire quickly and DB events remain
# the durable fallback across restarts.
_RECENT_BOT_CREATED: dict[tuple[int, int], float] = {}
_BACKGROUND_TASKS: set[asyncio.Task] = set()


@dataclass(slots=True)
class SendResult:
    ok: bool
    first_message_id: int | None
    message_ids: list[int]


def _remember_bot_created(chat_id: int, message_ids: Iterable[int]) -> None:
    now = time.monotonic()
    for message_id in message_ids:
        _RECENT_BOT_CREATED[(chat_id, int(message_id))] = now + 120.0


def is_recent_bot_created(chat_id: int, first_message_id: int, last_message_id: int) -> bool:
    now = time.monotonic()
    stale = [key for key, expiry in _RECENT_BOT_CREATED.items() if expiry <= now]
    for key in stale:
        _RECENT_BOT_CREATED.pop(key, None)
    return any(chat == chat_id and first_message_id <= message_id <= last_message_id for (chat, message_id) in _RECENT_BOT_CREATED)


def _trim_text(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text[:limit] if text else None


def _clean_body(text: str | None, entities: list[dict] | None, limit: int) -> tuple[str | None, list[dict] | None]:
    cleaned, cleaned_entities = strip_visible_links_with_entities(text, entities)
    if not cleaned:
        return None, None
    if cleaned_entities:
        # Do not strip whitespace after entity offsets have been remapped; that would
        # invalidate offsets. Telegram content is already within the platform limit.
        if len(cleaned) > limit:
            return cleaned[:limit], None
        return cleaned, cleaned_entities
    return _trim_text(cleaned, limit), None


def _join_with_footer(body: str | None, footer: str, limit: int) -> str:
    body = (body or '').strip()
    text = f'{body}\n\n{footer}' if body else footer
    if len(text) <= limit:
        return text
    room = max(0, limit - len(footer) - 8)
    if room <= 0:
        return footer[:limit]
    return f'{body[:room].rstrip()}...\n\n{footer}'


def _entity_models(raw: list[dict] | None) -> list[MessageEntity] | None:
    if not raw:
        return None
    return [MessageEntity(**item) for item in raw]


def _reply_markup(raw: dict | None) -> InlineKeyboardMarkup | None:
    if not raw:
        return None
    try:
        return InlineKeyboardMarkup(**raw)
    except Exception:
        logger.warning('invalid stored reply markup; skipping')
        return None


def _item_to_input_media(item: PostItem, caption: str | None, caption_entities: list[MessageEntity] | None):
    if item.media_type == 'photo' and item.file_id:
        return InputMediaPhoto(media=item.file_id, caption=caption, caption_entities=caption_entities)
    if item.media_type == 'video' and item.file_id:
        return InputMediaVideo(media=item.file_id, caption=caption, caption_entities=caption_entities)
    if item.media_type == 'document' and item.file_id:
        return InputMediaDocument(media=item.file_id, caption=caption, caption_entities=caption_entities)
    if item.media_type == 'audio' and item.file_id:
        return InputMediaAudio(media=item.file_id, caption=caption, caption_entities=caption_entities)
    return None


def chunks(items: list[PostItem], size: int = 10) -> Iterable[list[PostItem]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def format_footer(language: str, channel: PairChannel, message_id: int) -> str:
    return t(
        language,
        'footer',
        channel_title=channel.title,
        channel_link=channel_link_from_pair_channel(channel),
        post_link=post_link(channel.chat_id, message_id, channel.username),
    )


async def _retry_send_call(call):
    """Retry only explicit Telegram flood-wait responses.

    A network error is ambiguous for non-idempotent sendMessage/sendMediaGroup: the
    server may have accepted the request even though the client did not receive the
    response. Retrying those calls can create duplicate posts.
    """
    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        try:
            return await call()
        except TelegramRetryAfter as exc:
            if attempt >= MAX_SEND_ATTEMPTS:
                raise
            # The API tells us exactly how long to wait.
            await asyncio.sleep(max(0.5, float(exc.retry_after)))


async def _retry_edit_call(call):
    """Edits are idempotent enough to retry on transient network failures."""
    last_exc = None
    for attempt in range(1, MAX_EDIT_ATTEMPTS + 1):
        try:
            return await call()
        except TelegramRetryAfter as exc:
            last_exc = exc
            if attempt >= MAX_EDIT_ATTEMPTS:
                raise
            await asyncio.sleep(max(0.5, float(exc.retry_after)))
        except TelegramNetworkError as exc:
            last_exc = exc
            if attempt >= MAX_EDIT_ATTEMPTS:
                raise
            await asyncio.sleep(2 ** (attempt - 1))
    if last_exc:
        raise last_exc
    raise RuntimeError('edit retry failed without exception')


async def send_post_unit(bot: Bot, unit: PostUnit, to_chat_id: int) -> SendResult:
    items = list(unit.items)
    if not items:
        logger.warning('post unit has no items', extra={'post_unit_id': unit.id})
        return SendResult(False, None, [])

    if unit.post_type == 'album' and len(items) >= 2:
        created_ids: list[int] = []
        first_created_id: int | None = None
        try:
            for group in chunks(items, 10):
                media = []
                for item in group:
                    caption, caption_entities = _clean_body(item.caption, item.caption_entities, CAPTION_LIMIT)
                    input_media = _item_to_input_media(item, caption, _entity_models(caption_entities))
                    if input_media:
                        media.append(input_media)
                if not media:
                    continue
                sent = await _retry_send_call(lambda: bot.send_media_group(chat_id=to_chat_id, media=media))
                ids = [message.message_id for message in sent]
                created_ids.extend(ids)
                if first_created_id is None and ids:
                    first_created_id = ids[0]
                _remember_bot_created(to_chat_id, ids)

                # Bot API media groups do not accept inline keyboards on
                # sendMediaGroup. Apply per-item keyboards after the group exists.
                for sent_message, source_item in zip(sent, group):
                    markup = _reply_markup(source_item.reply_markup)
                    if not markup:
                        continue
                    try:
                        await _retry_edit_call(
                            lambda sent_message=sent_message, markup=markup: bot.edit_message_reply_markup(
                                chat_id=to_chat_id,
                                message_id=sent_message.message_id,
                                reply_markup=markup,
                            )
                        )
                    except Exception:
                        logger.exception(
                            'failed to restore album reply markup',
                            extra={'to_chat_id': to_chat_id, 'message_id': sent_message.message_id},
                        )
            return SendResult(bool(created_ids), first_created_id, created_ids)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.exception('telegram album send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
            return SendResult(False, first_created_id, created_ids)
        except Exception:
            logger.exception('unexpected album send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
            return SendResult(False, first_created_id, created_ids)

    first = items[0]
    try:
        if first.media_type == 'text':
            text, entities = _clean_body(first.text or unit.text, first.entities, TEXT_LIMIT)
            text = text or EMPTY_TEXT_PLACEHOLDER
            sent = await _retry_send_call(
                lambda: bot.send_message(
                    chat_id=to_chat_id,
                    text=text,
                    entities=_entity_models(entities),
                    disable_web_page_preview=True,
                    reply_markup=_reply_markup(first.reply_markup),
                )
            )
        else:
            caption, caption_entities = _clean_body(first.caption or unit.caption or unit.text, first.caption_entities, CAPTION_LIMIT)
            markup = _reply_markup(first.reply_markup)
            if first.media_type == 'photo' and first.file_id:
                sent = await _retry_send_call(lambda: bot.send_photo(to_chat_id, first.file_id, caption=caption, caption_entities=_entity_models(caption_entities), reply_markup=markup))
            elif first.media_type == 'video' and first.file_id:
                sent = await _retry_send_call(lambda: bot.send_video(to_chat_id, first.file_id, caption=caption, caption_entities=_entity_models(caption_entities), reply_markup=markup))
            elif first.media_type == 'document' and first.file_id:
                sent = await _retry_send_call(lambda: bot.send_document(to_chat_id, first.file_id, caption=caption, caption_entities=_entity_models(caption_entities), reply_markup=markup))
            elif first.media_type == 'audio' and first.file_id:
                sent = await _retry_send_call(lambda: bot.send_audio(to_chat_id, first.file_id, caption=caption, caption_entities=_entity_models(caption_entities), reply_markup=markup))
            else:
                logger.warning('unsupported media skipped', extra={'post_unit_id': unit.id, 'media_type': first.media_type})
                return SendResult(False, None, [])
        _remember_bot_created(to_chat_id, [sent.message_id])
        return SendResult(True, sent.message_id, [sent.message_id])
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.exception('telegram send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
        return SendResult(False, None, [])
    except Exception:
        logger.exception('unexpected send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
        return SendResult(False, None, [])


async def edit_post_unit_footer(bot: Bot, unit: PostUnit, chat_id: int, message_id: int, footer: str) -> bool:
    items = list(unit.items)
    if not items:
        return False
    first = items[0]
    for attempt in range(1, MAX_EDIT_ATTEMPTS + 1):
        try:
            if first.media_type == 'text':
                body, entities = _clean_body(first.text or unit.text, first.entities, TEXT_LIMIT)
                final_text = _join_with_footer(body, footer, TEXT_LIMIT)
                kwargs = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'text': final_text,
                    'disable_web_page_preview': True,
                }
                if entities and len(final_text) == len((body or '')) + 2 + len(footer):
                    kwargs['entities'] = _entity_models(entities)
                await bot.edit_message_text(**kwargs)
            else:
                body, entities = _clean_body(first.caption or unit.caption or unit.text, first.caption_entities, CAPTION_LIMIT)
                final_caption = _join_with_footer(body, footer, CAPTION_LIMIT)
                kwargs = {'chat_id': chat_id, 'message_id': message_id, 'caption': final_caption}
                if entities and len(final_caption) == len((body or '')) + 2 + len(footer):
                    kwargs['caption_entities'] = _entity_models(entities)
                await bot.edit_message_caption(**kwargs)
            return True
        except TelegramBadRequest as exc:
            if 'message is not modified' in str(exc).lower():
                return True
            logger.exception('telegram footer edit failed', extra={'chat_id': chat_id, 'message_id': message_id, 'post_unit_id': unit.id})
            return False
        except TelegramForbiddenError:
            logger.exception('telegram footer edit forbidden', extra={'chat_id': chat_id, 'message_id': message_id, 'post_unit_id': unit.id})
            return False
        except (TelegramRetryAfter, TelegramNetworkError) as exc:
            if attempt >= MAX_EDIT_ATTEMPTS:
                logger.exception('telegram footer edit retries exhausted', extra={'chat_id': chat_id, 'message_id': message_id, 'post_unit_id': unit.id})
                return False
            delay = float(exc.retry_after) if isinstance(exc, TelegramRetryAfter) else 2 ** (attempt - 1)
            await asyncio.sleep(delay)
        except Exception:
            logger.exception('unexpected footer edit failed', extra={'chat_id': chat_id, 'message_id': message_id, 'post_unit_id': unit.id})
            return False
    return False


async def _finish_loop(bot: Bot, loop_id: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        state = await repo.get_loop_state(loop_id)
        if not state or state.status not in {'waiting_footer', 'failed', 'footer_failed'}:
            return
        footer_unit = await repo.get_post_unit_by_first_message(state.origin_chat_id, state.origin_message_id)
        if not footer_unit:
            logger.error('footer source post unit missing', extra={'loop_id': loop_id})
            await repo.update_loop_delivery(loop_id, state.current_index, 'footer_failed')
            return

        route_ids = list(state.route_chat_ids or [])
        footer_ids = {int(k): int(v) for k, v in (state.footer_message_ids or {}).items()}
        all_ok = True
        for index, to_chat_id in enumerate(route_ids[1:], start=1):
            target_message_id = footer_ids.get(int(to_chat_id))
            if not target_message_id:
                continue
            previous_chat_id = int(route_ids[index - 1])
            if index == 1:
                previous_message_id = state.origin_message_id
            else:
                previous_message_id = footer_ids.get(previous_chat_id)
            if not previous_message_id:
                all_ok = False
                continue
            # Channel metadata is loaded through the owning pair.
            pair = await repo.get_pair(state.pair_id)
            if not pair:
                all_ok = False
                continue
            previous_channel = next((ch for ch in pair.channels if ch.chat_id == previous_chat_id), None)
            if not previous_channel:
                all_ok = False
                continue
            language = pair.user.language if pair.user else 'en'
            footer = format_footer(language, previous_channel, previous_message_id)
            if not await edit_post_unit_footer(bot, footer_unit, int(to_chat_id), target_message_id, footer):
                all_ok = False

        if state.status == 'failed':
            await repo.update_loop_delivery(loop_id, state.current_index, 'failed')
        else:
            await repo.update_loop_delivery(loop_id, state.current_index, 'done' if all_ok else 'footer_failed')


def _spawn(task) -> None:
    created = asyncio.create_task(task)
    _BACKGROUND_TASKS.add(created)
    created.add_done_callback(_BACKGROUND_TASKS.discard)


async def _finish_after_delay(bot: Bot, loop_id: str, delay: float) -> None:
    if delay > 0:
        await asyncio.sleep(delay)
    await _finish_loop(bot, loop_id)


async def resume_pending_loops(bot: Bot) -> None:
    """Recover delivery/footer work that was persisted before a restart."""
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        states = await repo.get_pending_loop_states()
    now = datetime.now(timezone.utc)
    for state in states:
        ready_at = state.footer_ready_at
        delay = max(0.0, (ready_at - now).total_seconds()) if ready_at else 0.0
        if state.status == 'waiting_footer':
            _spawn(_finish_after_delay(bot, state.loop_id, delay))
        elif state.status in {'failed', 'footer_failed'} and (state.footer_message_ids or {}):
            _spawn(_finish_after_delay(bot, state.loop_id, delay))
        elif state.status == 'running':
            # A restart means there is no live sender anymore. Never silently leave a
            # running state stuck forever; mark it failed and recover footers for any
            # channels that were already completed.
            logger.error('loop interrupted by process restart', extra={'loop_id': state.loop_id})
            async with AsyncSessionLocal() as session:
                repo2 = Repository(session)
                await repo2.update_loop_delivery(
                    state.loop_id,
                    state.current_index,
                    'failed',
                    state.created_message_ids or {},
                    state.footer_message_ids or {},
                    ready_at or datetime.now(timezone.utc),
                )
            if state.footer_message_ids:
                _spawn(_finish_after_delay(bot, state.loop_id, delay))


async def start_loop(
    bot: Bot,
    repo: Repository,
    pair: Pair,
    units: PostUnit | list[PostUnit],
    source_chat_id: int,
) -> bool:
    selected_units = units if isinstance(units, list) else [units]
    selected_units = [selected_unit for selected_unit in selected_units if selected_unit is not None]
    if not selected_units:
        return False

    route = build_route(pair, source_chat_id)
    if len(route) < 2:
        return False

    language = pair.user.language if pair.user else 'en'
    loop_id = uuid.uuid4().hex
    footer_unit = selected_units[-1]
    origin_message_id = footer_unit.first_message_id
    state = await repo.create_loop_state(
        loop_id=loop_id,
        pair_id=pair.id,
        origin_chat_id=source_chat_id,
        origin_message_id=origin_message_id,
        route_chat_ids=[ch.chat_id for ch in route],
        selected_unit_ids=[unit.id for unit in selected_units],
    )
    if not state or state.loop_id != loop_id:
        # Same original preview/message was already claimed by another trigger.
        return False

    created_by_channel: dict[str, list[int]] = {}
    footer_message_ids: dict[str, int] = {}

    for index, to_channel in enumerate(route[1:], start=1):
        target_all_ids: list[int] = []
        last_unit_first_id: int | None = None
        previous_channel = route[index - 1]
        previous_message_id = origin_message_id if index == 1 else footer_message_ids.get(str(previous_channel.chat_id))
        if previous_message_id is None:
            await repo.update_loop_delivery(loop_id, index, 'failed', created_by_channel, footer_message_ids)
            return False

        target_complete = True
        for selected_unit in selected_units:
            result = await send_post_unit(bot, selected_unit, to_channel.chat_id)
            if result.message_ids:
                target_all_ids.extend(result.message_ids)
                created_by_channel[str(to_channel.chat_id)] = list(target_all_ids)
                # Save the bot-origin events before the larger delivery-state update so
                # another polling worker can recognize a freshly-created post sooner.
                for created_id in result.message_ids:
                    await repo.save_loop_event(
                        loop_id=loop_id,
                        pair_id=pair.id,
                        origin_chat_id=source_chat_id,
                        origin_message_id=origin_message_id,
                        from_chat_id=previous_channel.chat_id,
                        from_message_id=previous_message_id,
                        to_chat_id=to_channel.chat_id,
                        to_message_id=created_id,
                        status='sent',
                    )
                # Persist partial progress immediately so a restart cannot unknowingly resend it.
                await repo.update_loop_delivery(loop_id, index, 'running', created_by_channel, footer_message_ids)
            if not result.ok:
                target_complete = False
                break
            last_unit_first_id = result.first_message_id

        if not target_complete:
            # Do not continue to later channels: their footer would otherwise point at
            # a channel that never received the previous hop.
            await repo.update_loop_delivery(loop_id, index, 'failed', created_by_channel, footer_message_ids, datetime.now(timezone.utc) + timedelta(seconds=FOOTER_EDIT_DELAY_SECONDS) if target_all_ids else None)
            if target_all_ids:
                _spawn(_finish_after_delay(bot, loop_id, FOOTER_EDIT_DELAY_SECONDS))
            return False

        if last_unit_first_id is None:
            await repo.update_loop_delivery(loop_id, index, 'failed', created_by_channel, footer_message_ids)
            return False

        footer_message_ids[str(to_channel.chat_id)] = last_unit_first_id
        await repo.update_loop_delivery(loop_id, index, 'running', created_by_channel, footer_message_ids)

    ready_at = datetime.now(timezone.utc) + timedelta(seconds=FOOTER_EDIT_DELAY_SECONDS)
    await repo.update_loop_delivery(
        loop_id,
        len(route) - 1,
        'waiting_footer',
        created_by_channel,
        footer_message_ids,
        ready_at,
    )
    _spawn(_finish_after_delay(bot, loop_id, FOOTER_EDIT_DELAY_SECONDS))
    return True


async def continue_loop_from_event(bot: Bot, repo: Repository, event: LoopEvent, current_unit: PostUnit) -> None:
    logger.debug('loop continuation ignored; persisted fan-out workflow is active', extra={'loop_id': event.loop_id})
