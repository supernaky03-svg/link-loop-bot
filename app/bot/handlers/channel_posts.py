from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.bot.services.album_service import AlbumCollector
from app.bot.services.movie_rule_service import save_messages_as_post_unit, select_unit_for_pair
from app.bot.services.repost_service import start_loop
from app.config import get_settings
from app.db.models import LoopEvent, PostUnit
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = Router(name="channel_posts")
settings = get_settings()
album_collector = AlbumCollector(settings.album_collect_delay_seconds)

BOT_CREATED_EVENT_RETRIES = 4
BOT_CREATED_EVENT_RETRY_DELAY_SECONDS = 0.25


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot) -> None:
    await album_collector.add(message, lambda messages: process_post_unit(messages, bot))


async def _find_bot_created_event(repo: Repository, unit: PostUnit) -> LoopEvent | None:
    """Find a loop event for a post that was created by this bot.

    Telegram can deliver the channel_post update very quickly after sendMessage /
    sendPhoto / sendMediaGroup. We retry briefly so a just-committed loop event is
    found before the post is treated as a new original post.
    """
    for attempt in range(BOT_CREATED_EVENT_RETRIES):
        event = await repo.get_loop_event_by_created_unit(
            unit.chat_id,
            unit.first_message_id,
            unit.last_message_id,
        )
        if event:
            return event
        if attempt < BOT_CREATED_EVENT_RETRIES - 1:
            await asyncio.sleep(BOT_CREATED_EVENT_RETRY_DELAY_SECONDS)
    return None


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

            # New fan-out workflow: bot-created posts are already part of a loop.
            # They should be ignored, not used to continue to the next channel and
            # not treated as fresh original posts.
            event = await _find_bot_created_event(repo, unit)
            if event:
                await repo.mark_processed(event.pair_id, unit.chat_id, unit.first_message_id)
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
            "channel post processing failed",
            extra={"chat_id": first.chat.id, "message_id": first.message_id},
        )
