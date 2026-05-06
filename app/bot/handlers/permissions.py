from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated

from app.bot.services.permission_service import handle_my_chat_member_update
from app.config import get_settings
from app.db.repository import Repository

logger = logging.getLogger(__name__)
router = Router(name='permissions')
settings = get_settings()


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, repo: Repository, bot: Bot) -> None:
    try:
        await handle_my_chat_member_update(bot, repo, settings, event)
    except Exception:
        logger.exception('my_chat_member handler failed', extra={'chat_id': event.chat.id})
