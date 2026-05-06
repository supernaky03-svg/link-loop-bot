from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.bot.services.album_service import AlbumCollector
from app.bot.services.movie_rule_service import save_messages_as_post_unit, select_unit_for_pair
from app.bot.services.repost_service import continue_loop_from_event, start_loop
from app.config import get_settings
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = Router(name='channel_posts')
settings = get_settings()
album_collector = AlbumCollector(settings.album_collect_delay_seconds)


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot) -> None:
    await album_collector.add(message, lambda messages: process_post_unit(messages, bot))


async def process_post_unit(messages: list[Message], bot: Bot) -> None:
    if not messages:
        return
    first = messages[0]
    try:
        async with AsyncSessionLocal() as session:
            repo = Repository(session)
            unit = await save_messages_as_post_unit(repo, settings, messages)
            if not unit:
                return

            # Bot-created messages are allowed to continue only the expected loop step.
            event = await repo.get_loop_event_by_created_message(unit.chat_id, unit.first_message_id)
            if event:
                if await repo.mark_processed(event.pair_id, unit.chat_id, unit.first_message_id):
                    await continue_loop_from_event(bot, repo, event, unit)
                return

            pairs = await repo.active_pairs_by_chat(unit.chat_id)
            for pair in pairs:
                if pair.is_paused or not pair.is_active:
                    continue
                if not await repo.mark_processed(pair.id, unit.chat_id, unit.first_message_id):
                    continue
                target_unit = await select_unit_for_pair(repo, pair.movie_rule, unit)
                if not target_unit:
                    continue
                await start_loop(bot, repo, pair, target_unit, source_chat_id=unit.chat_id)
    except Exception:
        logger.exception(
            'channel post processing failed',
            extra={'chat_id': first.chat.id, 'message_id': first.message_id},
        )
