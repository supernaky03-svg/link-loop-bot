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

router = Router(name="channel_posts")
settings = get_settings()
album_collector = AlbumCollector(settings.album_collect_delay_seconds)


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot) -> None:
    await album_collector.add(message, lambda messages: process_post_unit(messages, bot))


async def _find_created_loop_event_with_retry(
    repo: Repository,
    unit: PostUnit,
    *,
    attempts: int = 12,
    delay_seconds: float = 0.25,
) -> LoopEvent | None:
    """
    Bot-created channel_post updates can arrive before save_loop_event()
    commits to DB. Retry briefly before treating this post as a normal
    channel post.

    This is very important for Movie Rule ON:
    B repost post is not a video, so if we miss its loop_event, the chain
    stops at B and never reaches C.
    """
    for attempt in range(attempts):
        event = await repo.get_loop_event_by_created_unit(
            chat_id=unit.chat_id,
            first_message_id=unit.first_message_id,
            last_message_id=unit.last_message_id,
        )
        if event:
            return event

        if attempt < attempts - 1:
            await asyncio.sleep(delay_seconds)

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

            # 1) First priority:
            # If this post was created by this bot as part of an existing loop,
            # continue the expected next step. Do not apply Movie Rule selection here.
            event = await _find_created_loop_event_with_retry(repo, unit)
            if event:
                if await repo.mark_processed(event.pair_id, unit.chat_id, unit.first_message_id):
                    await continue_loop_from_event(bot, repo, event, unit)
                return

            # 2) Normal user-created/source channel post:
            # Apply pair settings. Important: select target_unit BEFORE mark_processed.
            # If Movie Rule ON and this unit is not a video, target_unit is None.
            # Marking it processed too early can block a late loop_event retry.
            pairs = await repo.active_pairs_by_chat(unit.chat_id)

            for pair in pairs:
                if pair.is_paused or not pair.is_active:
                    continue

                target_unit = await select_unit_for_pair(repo, pair.movie_rule, unit)
                if not target_unit:
                    continue

                if not await repo.mark_processed(pair.id, unit.chat_id, unit.first_message_id):
                    continue

                await start_loop(
                    bot=bot,
                    repo=repo,
                    pair=pair,
                    unit=target_unit,
                    source_chat_id=unit.chat_id,
                )

    except Exception:
        logger.exception(
            "channel post processing failed",
            extra={
                "chat_id": first.chat.id,
                "message_id": first.message_id,
            },
        )
