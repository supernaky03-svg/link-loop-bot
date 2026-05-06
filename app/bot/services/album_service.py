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
    """In-memory album collector for one-process polling deployments."""

    def __init__(self, delay_seconds: float):
        self.delay_seconds = delay_seconds
        self._buckets: dict[tuple[int, str], AlbumBucket] = defaultdict(AlbumBucket)
        self._lock = asyncio.Lock()

    async def add(self, message: Message, callback: AlbumCallback) -> None:
        if not message.media_group_id:
            await callback([message])
            return
        key = (message.chat.id, message.media_group_id)
        async with self._lock:
            bucket = self._buckets[key]
            bucket.messages.append(message)
            if not bucket.task:
                bucket.task = asyncio.create_task(self._flush_after_delay(key, callback))

    async def _flush_after_delay(self, key: tuple[int, str], callback: AlbumCallback) -> None:
        await asyncio.sleep(self.delay_seconds)
        async with self._lock:
            bucket = self._buckets.pop(key, None)
        if not bucket:
            return
        messages = sorted(bucket.messages, key=lambda msg: msg.message_id)
        try:
            await callback(messages)
        except Exception:
            logger.exception('album callback failed', extra={'chat_id': key[0], 'media_group_id': key[1]})
