from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.bot.services.album_service import AlbumCollector
from app.bot.services.movie_rule_service import save_messages_as_post_unit, select_units_for_pair
from app.bot.services.repost_service import is_recent_bot_created, start_loop
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


async def _find_bot_created_event(repo: Repository, first_message_id: int, last_message_id: int, chat_id: int) -> LoopEvent | None:
    """Check persisted loop events before inserting the post into the source cache.

    This ordering is important: bot-generated fan-out must never become a candidate
    for Movie Rule's "previous preview" search.
    """
    for attempt in range(BOT_CREATED_EVENT_RETRIES):
        event = await repo.get_loop_event_by_created_unit(chat_id, first_message_id, last_message_id)
        if event:
            return event
        if attempt < BOT_CREATED_EVENT_RETRIES - 1:
            await asyncio.sleep(BOT_CREATED_EVENT_RETRY_DELAY_SECONDS)
    return None


async def process_post_unit(messages: list[Message], bot: Bot) -> None:
    if not messages:
        return

    messages = sorted(messages, key=lambda msg: msg.message_id)
    first = messages[0]
    last = messages[-1]
    try:
        async with AsyncSessionLocal() as session:
            repo = Repository(session)

            # Race guard: Telegram may deliver our freshly-created post before the
            # transaction containing LoopEvent is committed.
            if is_recent_bot_created(first.chat.id, first.message_id, last.message_id):
                logger.debug(
                    "ignoring recently-created bot post",
                    extra={"chat_id": first.chat.id, "first_message_id": first.message_id},
                )
                return

            persisted_event = await _find_bot_created_event(
                repo,
                first_message_id=first.message_id,
                last_message_id=last.message_id,
                chat_id=first.chat.id,
            )
            if persisted_event:
                await repo.mark_processed(persisted_event.pair_id, first.chat.id, first.message_id)
                return

            # Only original posts enter PostUnit cache. This prevents fan-out copies
            # from becoming future Movie Rule previews.
            unit = await save_messages_as_post_unit(repo, settings, messages)
            if not unit:
                return

            pairs = await repo.active_pairs_by_chat(unit.chat_id)
            for pair in pairs:
                if pair.is_paused or not pair.is_active:
                    continue

                target_units = await select_units_for_pair(repo, pair.movie_rule, unit)
                if not target_units:
                    continue

                # Claim the trigger before starting the fan-out so concurrent updates
                # cannot launch the same pair twice.
                if not await repo.mark_processed(pair.id, unit.chat_id, unit.first_message_id):
                    continue

                await start_loop(
                    bot=bot,
                    repo=repo,
                    pair=pair,
                    units=target_units,
                    source_chat_id=unit.chat_id,
                )
    except Exception:
        logger.exception(
            "channel post processing failed",
            extra={"chat_id": first.chat.id, "message_id": first.message_id},
        )
