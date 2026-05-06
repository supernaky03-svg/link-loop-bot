from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.db.repository import Repository
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data['session'] = session
            data['repo'] = Repository(session)
            return await handler(event, data)


class UserAccessMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        if isinstance(event, Message):
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user
        if not from_user:
            return await handler(event, data)

        repo: Repository = data['repo']
        user, _created, rejected = await repo.get_or_create_user(
            tg_user_id=from_user.id,
            username=from_user.username,
            settings=self.settings,
        )
        if rejected or user is None:
            return None
        if user.is_banned and from_user.id not in self.settings.admin_ids:
            return None
        data['db_user'] = user
        data['language'] = user.language
        data['is_admin'] = from_user.id in self.settings.admin_ids
        return await handler(event, data)
