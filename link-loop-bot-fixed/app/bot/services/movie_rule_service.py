from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.config import Settings
from app.db.models import PostUnit
from app.db.repository import Repository

logger = logging.getLogger(__name__)
MOVIE_RULE_LOOKBACK_LIMIT = 30


def _dump_model(value: Any) -> dict | list | None:
    if value is None:
        return None
    if hasattr(value, 'model_dump'):
        return value.model_dump(exclude_none=True)
    if isinstance(value, list):
        return [item.model_dump(exclude_none=True) if hasattr(item, 'model_dump') else item for item in value]
    return value


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
    items: list[dict] = []
    has_video = False
    first_text = None
    first_caption = None
    for msg in messages:
        media_type, file_id, item_has_video = message_media_info(msg)
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
                'entities': _dump_model(msg.entities),
                'caption_entities': _dump_model(msg.caption_entities),
                'reply_markup': _dump_model(msg.reply_markup),
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
        logger.exception('failed to save post unit', extra={'chat_id': first.chat.id, 'message_id': first.message_id})
        return None


def _unit_items(unit: PostUnit) -> list:
    return list(getattr(unit, 'items', []) or [])


def _has_text(value: str | None) -> bool:
    return bool((value or '').strip())


def _unit_has_any_text(unit: PostUnit) -> bool:
    if _has_text(unit.text) or _has_text(unit.caption):
        return True
    return any(_has_text(item.text) or _has_text(item.caption) for item in _unit_items(unit))


def _unit_has_video(unit: PostUnit) -> bool:
    if unit.has_video:
        return True
    return any(item.media_type == 'video' for item in _unit_items(unit))


def _unit_is_text_only(unit: PostUnit) -> bool:
    items = _unit_items(unit)
    if items:
        return all(item.media_type == 'text' for item in items)
    return _has_text(unit.text) and not _has_text(unit.caption)


def _unit_is_image_or_album(unit: PostUnit) -> bool:
    if unit.post_type == 'album':
        return True
    return any(item.media_type == 'photo' for item in _unit_items(unit))


def _unit_is_text_photo_or_album(unit: PostUnit) -> bool:
    return _unit_is_image_or_album(unit) and _unit_has_any_text(unit)


async def select_units_for_pair(
    repo: Repository,
    pair_movie_rule: bool,
    current_unit: PostUnit,
) -> list[PostUnit]:
    """Select the content to loop.

    Movie Rule ON treats a text+photo/album preview as the movie unit. A preview
    can be claimed only once per pair/source message because LoopState has a DB
    unique key on (pair, origin_chat, origin_message). This makes
    Preview + Video + Video + Video => one loop, even under concurrent updates.
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
        return []

    for previous in previous_units:
        if _unit_has_video(previous) or _unit_is_text_only(previous):
            continue
        if not _unit_is_text_photo_or_album(previous):
            continue

        logger.info(
            'movie rule selected preview',
            extra={
                'chat_id': current_unit.chat_id,
                'trigger_message_id': current_unit.first_message_id,
                'preview_message_id': previous.first_message_id,
            },
        )
        return [previous]

    return []


async def select_unit_for_pair(repo: Repository, pair_movie_rule: bool, current_unit: PostUnit) -> PostUnit | None:
    units = await select_units_for_pair(repo, pair_movie_rule, current_unit)
    return units[-1] if units else None
