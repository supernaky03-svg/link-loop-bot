from __future__ import annotations

import asyncio
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
)

from app.bot.services.language_service import t
from app.bot.services.link_service import (
    channel_link_from_pair_channel,
    post_link,
    strip_visible_links,
)
from app.bot.services.pair_service import build_route
from app.db.models import LoopEvent, Pair, PairChannel, PostItem, PostUnit
from app.db.repository import Repository

logger = logging.getLogger(__name__)

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
FOOTER_EDIT_DELAY_SECONDS = 15
EMPTY_TEXT_PLACEHOLDER = "\u2063"  # invisible placeholder for text posts that become empty after link stripping


def _trim_text(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    return text[:limit]


def _clean_body(text: str | None, limit: int) -> str | None:
    return _trim_text(strip_visible_links(text), limit)


def _join_with_footer(body: str | None, footer: str, limit: int) -> str:
    body = (body or "").strip()
    text = f"{body}\n\n{footer}" if body else footer
    if len(text) <= limit:
        return text

    room = max(0, limit - len(footer) - 8)
    if room <= 0:
        return footer[:limit]
    return f"{body[:room].rstrip()}...\n\n{footer}"


def _item_to_input_media(item: PostItem, caption: str | None):
    if item.media_type == "photo" and item.file_id:
        return InputMediaPhoto(media=item.file_id, caption=caption)
    if item.media_type == "video" and item.file_id:
        return InputMediaVideo(media=item.file_id, caption=caption)
    if item.media_type == "document" and item.file_id:
        return InputMediaDocument(media=item.file_id, caption=caption)
    if item.media_type == "audio" and item.file_id:
        return InputMediaAudio(media=item.file_id, caption=caption)
    return None


def chunks(items: list[PostItem], size: int = 10) -> Iterable[list[PostItem]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def format_footer(language: str, channel: PairChannel, message_id: int) -> str:
    return t(
        language,
        "footer",
        channel_title=channel.title,
        channel_link=channel_link_from_pair_channel(channel),
        post_link=post_link(channel.chat_id, message_id, channel.username),
    )


async def send_post_unit(bot: Bot, unit: PostUnit, to_chat_id: int) -> int | None:
    """Send one cached post unit without footer and return the first created message id.

    Visible links are stripped at send time so the repost never exposes the original
    link text while waiting for the delayed footer edit.
    """
    items = list(unit.items)
    if not items:
        logger.warning("post unit has no items", extra={"post_unit_id": unit.id})
        return None

    first = items[0]
    try:
        if unit.post_type == "album" and len(items) >= 2:
            first_created_id: int | None = None
            for group in chunks(items, 10):
                media = []
                for item in group:
                    caption = _clean_body(item.caption, CAPTION_LIMIT)
                    input_media = _item_to_input_media(item, caption)
                    if input_media:
                        media.append(input_media)

                if not media:
                    continue

                sent = await bot.send_media_group(chat_id=to_chat_id, media=media)
                if sent and first_created_id is None:
                    first_created_id = sent[0].message_id

            return first_created_id

        if first.media_type == "text":
            text = _clean_body(first.text or unit.text, TEXT_LIMIT) or EMPTY_TEXT_PLACEHOLDER
            sent = await bot.send_message(
                chat_id=to_chat_id,
                text=text,
                disable_web_page_preview=True,
            )
            return sent.message_id

        caption = _clean_body(first.caption or unit.caption or unit.text, CAPTION_LIMIT)
        if first.media_type == "photo" and first.file_id:
            sent = await bot.send_photo(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == "video" and first.file_id:
            sent = await bot.send_video(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == "document" and first.file_id:
            sent = await bot.send_document(to_chat_id, first.file_id, caption=caption)
        elif first.media_type == "audio" and first.file_id:
            sent = await bot.send_audio(to_chat_id, first.file_id, caption=caption)
        else:
            logger.warning(
                "unsupported media skipped",
                extra={"post_unit_id": unit.id, "media_type": first.media_type},
            )
            return None

        return sent.message_id
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.exception(
            "telegram send failed",
            extra={"to_chat_id": to_chat_id, "post_unit_id": unit.id},
        )
        return None
    except Exception:
        logger.exception(
            "unexpected send failed",
            extra={"to_chat_id": to_chat_id, "post_unit_id": unit.id},
        )
        return None


async def edit_post_unit_footer(
    bot: Bot,
    unit: PostUnit,
    chat_id: int,
    message_id: int,
    footer: str,
) -> bool:
    """Edit the already-created post and append the delayed footer.

    For albums, only the first created media item gets the footer caption.
    """
    items = list(unit.items)
    if not items:
        return False

    first = items[0]
    try:
        if first.media_type == "text":
            body = _clean_body(first.text or unit.text, TEXT_LIMIT)
            text = _join_with_footer(body, footer, TEXT_LIMIT)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                disable_web_page_preview=True,
            )
            return True

        body = _clean_body(first.caption or unit.caption or unit.text, CAPTION_LIMIT)
        caption = _join_with_footer(body, footer, CAPTION_LIMIT)
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
        )
        return True
    except TelegramBadRequest as exc:
        # Telegram returns "message is not modified" if caption/text is already the same.
        if "message is not modified" in str(exc).lower():
            return True
        logger.exception(
            "telegram footer edit failed",
            extra={"chat_id": chat_id, "message_id": message_id, "post_unit_id": unit.id},
        )
        return False
    except TelegramForbiddenError:
        logger.exception(
            "telegram footer edit forbidden",
            extra={"chat_id": chat_id, "message_id": message_id, "post_unit_id": unit.id},
        )
        return False
    except Exception:
        logger.exception(
            "unexpected footer edit failed",
            extra={"chat_id": chat_id, "message_id": message_id, "post_unit_id": unit.id},
        )
        return False


async def start_loop(
    bot: Bot,
    repo: Repository,
    pair: Pair,
    unit: PostUnit,
    source_chat_id: int,
) -> None:
    """Fan out one original post to every other channel, then edit footers later.

    New workflow:
    1. Build route with the original source channel always first.
    2. Send the original post to every remaining channel immediately.
    3. Strip visible links during send.
    4. Save created message IDs by channel.
    5. Wait 15 seconds.
    6. Edit each created post with previous channel + previous post link footer.

    This avoids the old Channel B update -> Channel C continuation dependency.
    """
    route = build_route(pair, source_chat_id)
    if len(route) < 2:
        return

    language = pair.user.language if pair.user else "en"
    loop_id = uuid.uuid4().hex
    origin_message_id = unit.first_message_id

    await repo.create_loop_state(
        loop_id=loop_id,
        pair_id=pair.id,
        origin_chat_id=source_chat_id,
        origin_message_id=origin_message_id,
        route_chat_ids=[ch.chat_id for ch in route],
    )

    created_message_ids: dict[int, int] = {source_chat_id: origin_message_id}

    # Send phase: send to all targets first. Do not stop the whole route if one
    # target fails; later channels can still receive the original content.
    for index, to_channel in enumerate(route[1:], start=1):
        created_id = await send_post_unit(bot, unit, to_channel.chat_id)
        if created_id is None:
            logger.warning(
                "fan-out send failed",
                extra={"pair_id": pair.id, "loop_id": loop_id, "to_chat_id": to_channel.chat_id},
            )
            continue

        created_message_ids[to_channel.chat_id] = created_id

        previous_channel = route[index - 1]
        previous_message_id = created_message_ids.get(previous_channel.chat_id, origin_message_id)
        await repo.save_loop_event(
            loop_id=loop_id,
            pair_id=pair.id,
            origin_chat_id=source_chat_id,
            origin_message_id=origin_message_id,
            from_chat_id=previous_channel.chat_id,
            from_message_id=previous_message_id,
            to_chat_id=to_channel.chat_id,
            to_message_id=created_id,
            status="sent",
        )

    if len(created_message_ids) <= 1:
        await repo.update_loop_index(loop_id, 0, status="done")
        return

    await repo.update_loop_index(loop_id, len(route) - 1, status="sent")
    await asyncio.sleep(FOOTER_EDIT_DELAY_SECONDS)

    # Edit phase: each target gets the link of the previous route channel/post.
    for index, to_channel in enumerate(route[1:], start=1):
        created_id = created_message_ids.get(to_channel.chat_id)
        if created_id is None:
            continue

        previous_channel = route[index - 1]
        previous_message_id = created_message_ids.get(previous_channel.chat_id)
        if previous_message_id is None:
            logger.warning(
                "previous hop missing; skip delayed footer edit",
                extra={
                    "pair_id": pair.id,
                    "loop_id": loop_id,
                    "to_chat_id": to_channel.chat_id,
                    "previous_chat_id": previous_channel.chat_id,
                },
            )
            continue

        footer = format_footer(language, previous_channel, previous_message_id)
        await edit_post_unit_footer(
            bot=bot,
            unit=unit,
            chat_id=to_channel.chat_id,
            message_id=created_id,
            footer=footer,
        )

    await repo.update_loop_index(loop_id, len(route) - 1, status="done")


async def continue_loop_from_event(
    bot: Bot,
    repo: Repository,
    event: LoopEvent,
    current_unit: PostUnit,
) -> None:
    """Backward-compatible no-op.

    The old workflow continued a loop when a bot-created channel post update came
    back from Telegram. The new workflow sends every target first and only edits
    footers later, so bot-created updates must be ignored by the handler.
    """
    logger.debug(
        "loop continuation ignored; fan-out workflow is active",
        extra={"loop_id": event.loop_id, "to_chat_id": event.to_chat_id},
    )
