from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from aiogram.types import Message

logger = logging.getLogger(__name__)

AlbumCallback = Callable[[list[Message]], Awaitable[None]]


@dataclass
class AlbumBucket:
    messages: list[Message] = field(default_factory=list)
    task: asyncio.Task | None = None


class AlbumCollector:
    """Collect an incoming Telegram media group by inactivity, not first-message timing."""

    MAX_ALBUM_ITEMS = 10

    def __init__(self, delay_seconds: float):
        self.delay_seconds = max(0.1, float(delay_seconds))
        self._buckets: dict[tuple[int, str], AlbumBucket] = defaultdict(AlbumBucket)
        self._lock = asyncio.Lock()

    async def add(self, message: Message, callback: AlbumCallback) -> None:
        if not message.media_group_id:
            await callback([message])
            return

        key = (message.chat.id, message.media_group_id)
        flush_now = False
        async with self._lock:
            bucket = self._buckets[key]
            if all(existing.message_id != message.message_id for existing in bucket.messages):
                bucket.messages.append(message)

            # Telegram media groups are capped at 10. Once all 10 arrive we do not
            # need to wait for the inactivity timer.
            if len(bucket.messages) >= self.MAX_ALBUM_ITEMS:
                flush_now = True
                old_task = bucket.task
                bucket.task = None
                if old_task and not old_task.done():
                    old_task.cancel()
            else:
                old_task = bucket.task
                if old_task and not old_task.done():
                    old_task.cancel()
                bucket.task = asyncio.create_task(self._flush_after_delay(key, callback))

        if flush_now:
            await self._flush(key, callback)

    async def _flush_after_delay(self, key: tuple[int, str], callback: AlbumCallback) -> None:
        try:
            await asyncio.sleep(self.delay_seconds)
            await self._flush(key, callback)
        except asyncio.CancelledError:
            raise

    async def _flush(self, key: tuple[int, str], callback: AlbumCallback) -> None:
        async with self._lock:
            bucket = self._buckets.pop(key, None)
        if not bucket or not bucket.messages:
            return

        messages = sorted(bucket.messages, key=lambda msg: msg.message_id)
        try:
            await callback(messages)
        except Exception:
            logger.exception("album callback failed", extra={"chat_id": key[0], "media_group_id": key[1]})
