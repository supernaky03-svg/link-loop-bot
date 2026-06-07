from __future__ import annotations

import logging

from aiogram.types import Message

from app.config import Settings
from app.db.models import PostUnit
from app.db.repository import Repository

logger = logging.getLogger(__name__)


def message_media_info(message: Message) -> tuple[str, str | None, bool]:
    if message.photo:
        return 'photo', message.photo[-1].file_id, False
    if message.video:
        return 'video', message.video.file_id, True
    if message.document:
        return 'document', message.document.file_id, False
    if message.audio:
        return 'audio', message.audio.file_id, False
    if message.text:
        return 'text', None, False
    return 'unsupported', None, False


def _unit_key(messages: list[Message]) -> str:
    first = messages[0]
    if first.media_group_id:
        return f'{first.chat.id}:album:{first.media_group_id}'
    return f'{first.chat.id}:single:{first.message_id}'


async def save_messages_as_post_unit(
    repo: Repository,
    settings: Settings,
    messages: list[Message],
) -> PostUnit | None:
    if not messages:
        return None
    messages = sorted(messages, key=lambda msg: msg.message_id)
    first = messages[0]
    last = messages[-1]
    items = []
    has_video = False
    first_text = None
    first_caption = None
    for msg in messages:
        media_type, file_id, item_has_video = message_media_info(msg)
        if media_type == 'unsupported':
            logger.info(
                'unsupported channel post cached as unsupported',
                extra={'chat_id': msg.chat.id, 'message_id': msg.message_id},
            )
        has_video = has_video or item_has_video
        if first_text is None and msg.text:
            first_text = msg.text
        if first_caption is None and msg.caption:
            first_caption = msg.caption
        items.append(
            {
                'message_id': msg.message_id,
                'media_type': media_type,
                'file_id': file_id,
                'caption': msg.caption,
                'text': msg.text,
            }
        )
    try:
        return await repo.save_post_unit(
            chat_id=first.chat.id,
            unit_key=_unit_key(messages),
            first_message_id=first.message_id,
            last_message_id=last.message_id,
            media_group_id=first.media_group_id,
            post_type='album' if first.media_group_id else 'single',
            has_video=has_video,
            text=first_text,
            caption=first_caption,
            items=items,
            cache_limit=settings.post_cache_limit_per_channel,
        )
    except Exception:
        logger.exception(
            'failed to save post unit',
            extra={'chat_id': first.chat.id, 'message_id': first.message_id},
        )
        return None


def _unit_items(unit: PostUnit) -> list:
    return list(getattr(unit, "items", []) or [])


def _has_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _unit_has_any_text(unit: PostUnit) -> bool:
    if _has_text(unit.text) or _has_text(unit.caption):
        return True

    return any(_has_text(item.text) or _has_text(item.caption) for item in _unit_items(unit))


def _unit_has_video(unit: PostUnit) -> bool:
    if unit.has_video:
        return True
    return any(item.media_type == "video" for item in _unit_items(unit))


def _unit_is_text_only(unit: PostUnit) -> bool:
    items = _unit_items(unit)

    if items:
        return all(item.media_type == "text" for item in items)

    return _has_text(unit.text) and not _has_text(unit.caption)


def _unit_is_image_or_album(unit: PostUnit) -> bool:
    """
    Movie preview media:
    - album/media group
    - single photo/image post

    Video units are checked and skipped before this helper is used.
    """
    if unit.post_type == "album":
        return True

    return any(item.media_type == "photo" for item in _unit_items(unit))


def _unit_is_text_photo_or_album(unit: PostUnit) -> bool:
    """Return True for the wanted movie-preview post: text/caption + photo/album."""
    return _unit_is_image_or_album(unit) and _unit_has_any_text(unit)


MOVIE_RULE_LOOKBACK_LIMIT = 30


async def select_units_for_pair(
    repo: Repository,
    pair_movie_rule: bool,
    current_unit: PostUnit,
) -> list[PostUnit]:
    """
    Movie Rule behavior:

    OFF:
        loop current unit.

    ON:
        only video trigger is used.

        The video itself is never looped. Starting from the post immediately
        above the video, search backwards until a text+photo/album preview post
        is found, then loop only that preview post.

        skipped while searching:
        - video posts
        - text-only posts
        - unsupported/non-preview units
    """
    if not pair_movie_rule:
        return [current_unit]

    if not _unit_has_video(current_unit):
        return []

    previous_units = await repo.get_previous_post_units(
        chat_id=current_unit.chat_id,
        before_message_id=current_unit.first_message_id,
        limit=MOVIE_RULE_LOOKBACK_LIMIT,
    )

    if not previous_units:
        logger.warning(
            "movie rule previous post not found",
            extra={
                "chat_id": current_unit.chat_id,
                "message_id": current_unit.first_message_id,
            },
        )
        return []

    for previous in previous_units:
        if _unit_has_video(previous):
            logger.info(
                "movie rule skipped previous video while searching preview",
                extra={
                    "chat_id": current_unit.chat_id,
                    "trigger_message_id": current_unit.first_message_id,
                    "skipped_message_id": previous.first_message_id,
                },
            )
            continue

        if _unit_is_text_only(previous):
            logger.info(
                "movie rule skipped previous text-only while searching preview",
                extra={
                    "chat_id": current_unit.chat_id,
                    "trigger_message_id": current_unit.first_message_id,
                    "skipped_message_id": previous.first_message_id,
                },
            )
            continue

        if _unit_is_text_photo_or_album(previous):
            logger.info(
                "movie rule selected text+photo/album preview",
                extra={
                    "chat_id": current_unit.chat_id,
                    "trigger_message_id": current_unit.first_message_id,
                    "selected_message_id": previous.first_message_id,
                },
            )
            return [previous]

        logger.info(
            "movie rule skipped non-preview previous unit",
            extra={
                "chat_id": current_unit.chat_id,
                "trigger_message_id": current_unit.first_message_id,
                "skipped_message_id": previous.first_message_id,
                "post_type": previous.post_type,
            },
        )

    logger.warning(
        "movie rule text+photo/album preview not found in lookback window",
        extra={
            "chat_id": current_unit.chat_id,
            "trigger_message_id": current_unit.first_message_id,
            "lookback_limit": MOVIE_RULE_LOOKBACK_LIMIT,
        },
    )
    return []


async def select_unit_for_pair(
    repo: Repository,
    pair_movie_rule: bool,
    current_unit: PostUnit,
) -> PostUnit | None:
    """
    Backward-compatible wrapper.
    New code should use select_units_for_pair().
    """
    units = await select_units_for_pair(repo, pair_movie_rule, current_unit)
    return units[-1] if units else None
