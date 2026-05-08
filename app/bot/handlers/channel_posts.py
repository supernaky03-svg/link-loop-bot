from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.bot.services.album_service import AlbumCollector
from app.bot.services.movie_rule_service import save_messages_as_post_unit, select_unit_for_pair
from app.bot.services.repost_service import continue_loop_from_event, start_loop
from app.config import get_settings
from app.db.models import LoopEvent, PostUnit
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = Router(name='channel_posts')
settings = get_settings()
album_collector = AlbumCollector(settings.album_collect_delay_seconds)

# Telegram can deliver the channel_post update for a bot-created repost before
# the loop event commit is visible in PostgreSQL. Without this short retry,
# Movie Rule ON may treat the reposted preview post as a normal non-video post
# and stop at the first repost channel instead of continuing the route.
LOOP_EVENT_RETRY_DELAYS = (0.15, 0.35, 0.75)


async def find_created_loop_event(repo: Repository, unit: PostUnit) -> LoopEvent | None:
    event = await repo.get_loop_event_by_created_unit(
        unit.chat_id,
        unit.first_message_id,
        unit.last_message_id,
    )
    if event:
        return event

    for delay in LOOP_EVENT_RETRY_DELAYS:
        await asyncio.sleep(delay)
        event = await repo.get_loop_event_by_created_unit(
            unit.chat_id,
            unit.first_message_id,
            unit.last_message_id,
        )
        if event:
            return event
    return None


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
            # We retry briefly because Telegram can deliver the channel_post update before
            # save_loop_event() has committed the created message id. This race is most
            # visible when Movie Rule is ON: the reposted preview is non-video, so without
            # the event match it stops at channel B and never reaches channel C.
            event = await find_created_loop_event(repo, unit)
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
