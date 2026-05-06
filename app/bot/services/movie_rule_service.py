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


async def select_unit_for_pair(repo: Repository, pair_movie_rule: bool, current_unit: PostUnit) -> PostUnit | None:
    if not pair_movie_rule:
        return current_unit
    if not current_unit.has_video:
        return None
    previous = await repo.get_previous_post_unit(current_unit.chat_id, current_unit.first_message_id)
    if not previous:
        logger.warning(
            'movie rule previous post not found',
            extra={'chat_id': current_unit.chat_id, 'message_id': current_unit.first_message_id},
        )
    return previous
