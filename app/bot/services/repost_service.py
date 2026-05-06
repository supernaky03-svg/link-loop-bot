from __future__ import annotations

import logging
import uuid
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from app.bot.services.language_service import t
from app.bot.services.link_service import channel_link_from_pair_channel, post_link, strip_visible_links
from app.bot.services.pair_service import build_route
from app.db.models import LoopEvent, Pair, PairChannel, PostItem, PostUnit
from app.db.repository import Repository

logger = logging.getLogger(__name__)

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024


def _join_with_footer(body: str | None, footer: str, limit: int) -> str:
    body = (strip_visible_links(body) or '').strip()
    text = f'{body}\n\n{footer}' if body else footer
    if len(text) <= limit:
        return text
    room = max(0, limit - len(footer) - 8)
    return f'{body[:room].rstrip()}...\n\n{footer}'


def _item_to_input_media(item: PostItem, caption: str | None):
    if item.media_type == 'photo' and item.file_id:
        return InputMediaPhoto(media=item.file_id, caption=caption)
    if item.media_type == 'video' and item.file_id:
        return InputMediaVideo(media=item.file_id, caption=caption)
    if item.media_type == 'document' and item.file_id:
        return InputMediaDocument(media=item.file_id, caption=caption)
    if item.media_type == 'audio' and item.file_id:
        return InputMediaAudio(media=item.file_id, caption=caption)
    return None


def chunks(items: list[PostItem], size: int = 10) -> Iterable[list[PostItem]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def format_footer(language: str, channel: PairChannel, message_id: int) -> str:
    return t(
        language,
        'footer',
        channel_title=channel.title,
        channel_link=channel_link_from_pair_channel(channel),
        post_link=post_link(channel.chat_id, message_id, channel.username),
    )


async def send_post_unit(bot: Bot, unit: PostUnit, to_chat_id: int, footer: str) -> int | None:
    """Send one cached post unit and return first created Telegram message id."""
    items = list(unit.items)
    if not items:
        logger.warning('post unit has no items', extra={'post_unit_id': unit.id})
        return None

    first = items[0]
    try:
        if unit.post_type == 'album' and len(items) >= 2:
            first_created_id: int | None = None
            footer_used = False
            for group in chunks(items, 10):
                media = []
                for idx, item in enumerate(group):
                    caption: str | None = None
                    if not footer_used and idx == 0:
                        caption = _join_with_footer(item.caption or unit.caption or unit.text, footer, CAPTION_LIMIT)
                        footer_used = True
                    elif item.caption:
                        cleaned_caption = strip_visible_links(item.caption)
                        caption = cleaned_caption[:CAPTION_LIMIT] if cleaned_caption else None
                    input_media = _item_to_input_media(item, caption)
                    if input_media:
                        media.append(input_media)
                if not media:
                    continue
                sent = await bot.send_media_group(chat_id=to_chat_id, media=media)
                if sent and first_created_id is None:
                    first_created_id = sent[0].message_id
            return first_created_id

        if first.media_type == 'text':
            text = _join_with_footer(first.text or unit.text, footer, TEXT_LIMIT)
            sent = await bot.send_message(to_chat_id, text, disable_web_page_preview=True)
            return sent.message_id

        caption = _join_with_footer(first.caption or unit.caption or unit.text, footer, CAPTION_LIMIT)
        if first.media_type == 'photo' and first.file_id:
            sent = await bot.send_photo(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == 'video' and first.file_id:
            sent = await bot.send_video(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == 'document' and first.file_id:
            sent = await bot.send_document(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == 'audio' and first.file_id:
            sent = await bot.send_audio(to_chat_id, first.file_id, caption=caption)
        else:
            logger.warning(
                'unsupported media skipped',
                extra={'post_unit_id': unit.id, 'media_type': first.media_type},
            )
            return None
        return sent.message_id
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.exception('telegram send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
        return None
    except Exception:
        logger.exception('unexpected send failed', extra={'to_chat_id': to_chat_id, 'post_unit_id': unit.id})
        return None


async def start_loop(bot: Bot, repo: Repository, pair: Pair, unit: PostUnit, source_chat_id: int) -> None:
    route = build_route(pair, source_chat_id)
    if len(route) < 2:
        return
    loop_id = uuid.uuid4().hex
    await repo.create_loop_state(
        loop_id=loop_id,
        pair_id=pair.id,
        origin_chat_id=source_chat_id,
        origin_message_id=unit.first_message_id,
        route_chat_ids=[ch.chat_id for ch in route],
    )
    await _send_next_step(
        bot=bot,
        repo=repo,
        pair=pair,
        unit=unit,
        loop_id=loop_id,
        route=route,
        from_index=0,
        origin_chat_id=source_chat_id,
        origin_message_id=unit.first_message_id,
    )


async def continue_loop_from_event(
    bot: Bot,
    repo: Repository,
    event: LoopEvent,
    current_unit: PostUnit,
) -> None:
    pair = await repo.get_pair(event.pair_id)
    state = await repo.get_loop_state(event.loop_id)
    if not pair or not state or state.status != 'running' or pair.is_paused or not pair.is_active:
        return
    route_channels = {ch.chat_id: ch for ch in pair.channels if ch.is_active}
    route = [route_channels[cid] for cid in state.route_chat_ids if cid in route_channels]
    if len(route) < 2:
        await repo.update_loop_index(event.loop_id, state.current_index, status='done')
        return
    try:
        current_index = state.route_chat_ids.index(event.to_chat_id)
    except ValueError:
        logger.warning('created message is not in route', extra={'loop_id': event.loop_id})
        return
    if current_index >= len(route) - 1:
        await repo.update_loop_index(event.loop_id, current_index, status='done')
        return
    if state.current_index > current_index:
        return
    await _send_next_step(
        bot=bot,
        repo=repo,
        pair=pair,
        unit=current_unit,
        loop_id=event.loop_id,
        route=route,
        from_index=current_index,
        origin_chat_id=event.origin_chat_id,
        origin_message_id=event.origin_message_id,
    )


async def _send_next_step(
    bot: Bot,
    repo: Repository,
    pair: Pair,
    unit: PostUnit,
    loop_id: str,
    route: list[PairChannel],
    from_index: int,
    origin_chat_id: int,
    origin_message_id: int,
) -> None:
    if from_index >= len(route) - 1:
        await repo.update_loop_index(loop_id, from_index, status='done')
        return
    from_channel = route[from_index]
    to_channel = route[from_index + 1]
    footer = format_footer(pair.user.language if pair.user else 'en', from_channel, unit.first_message_id)
    created_id = await send_post_unit(bot, unit, to_channel.chat_id, footer)
    if created_id is None:
        logger.warning(
            'loop step send failed',
            extra={'pair_id': pair.id, 'loop_id': loop_id, 'to_chat_id': to_channel.chat_id},
        )
        return
    await repo.save_loop_event(
        loop_id=loop_id,
        pair_id=pair.id,
        origin_chat_id=origin_chat_id,
        origin_message_id=origin_message_id,
        from_chat_id=from_channel.chat_id,
        from_message_id=unit.first_message_id,
        to_chat_id=to_channel.chat_id,
        to_message_id=created_id,
    )
    await repo.update_loop_index(loop_id, from_index + 1, status='running')
