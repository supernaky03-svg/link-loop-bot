from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import ChatMemberUpdated

from app.bot.services.language_service import t
from app.bot.services.report_service import notify_user, send_admin_permission_report
from app.config import Settings
from app.db.repository import Repository

logger = logging.getLogger(__name__)


def _admin_can_post(event: ChatMemberUpdated) -> bool:
    new = event.new_chat_member
    status = new.status
    if status == 'creator':
        return True
    if status == 'administrator':
        return bool(getattr(new, 'can_post_messages', False))
    return False


def _old_admin_can_post(event: ChatMemberUpdated) -> bool:
    old = event.old_chat_member
    status = old.status
    if status == 'creator':
        return True
    if status == 'administrator':
        return bool(getattr(old, 'can_post_messages', False))
    return False


async def handle_my_chat_member_update(
    bot: Bot,
    repo: Repository,
    settings: Settings,
    event: ChatMemberUpdated,
) -> None:
    chat_id = event.chat.id
    channel_title = event.chat.title or event.chat.username or str(chat_id)
    old_ok = _old_admin_can_post(event)
    new_ok = _admin_can_post(event)

    if old_ok and not new_ok:
        pairs = await repo.pause_pairs_using_channel(chat_id, reason='bot_admin_removed')
        if not pairs:
            return
        for pair in pairs:
            await send_admin_permission_report(
                bot, repo, settings, pair, chat_id, channel_title, 'bot_admin_removed'
            )
            if pair.user:
                await notify_user(
                    bot,
                    pair.user.tg_user_id,
                    t(pair.user.language, 'permission_removed_user', channel_title=channel_title),
                )
        return

    if not old_ok and new_ok:
        pairs = await repo.mark_channel_admin_restored(chat_id)
        for pair in pairs:
            if pair.user:
                await notify_user(
                    bot,
                    pair.user.tg_user_id,
                    t(pair.user.language, 'permission_restored_user', channel_title=channel_title),
                )
