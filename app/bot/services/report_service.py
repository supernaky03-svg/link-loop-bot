from __future__ import annotations

import logging

from aiogram import Bot

from app.config import Settings
from app.db.models import Pair
from app.db.repository import Repository

logger = logging.getLogger(__name__)


async def send_admin_permission_report(
    bot: Bot,
    repo: Repository,
    settings: Settings,
    pair: Pair,
    chat_id: int,
    channel_title: str,
    report_type: str,
) -> None:
    username = f'@{pair.user.username}' if pair.user and pair.user.username else '-'
    text = (
        f'⚠️ Admin Permission Report\n\n'
        f'Type: {report_type}\n'
        f'Username: {username}\n'
        f'User ID: {pair.user.tg_user_id if pair.user else pair.user_id}\n'
        f'Pair Number: {pair.pair_no}\n'
        f'Channel Title: {channel_title}\n'
        f'Channel ID: {chat_id}'
    )
    await repo.create_admin_report(pair.user_id, pair.id, chat_id, report_type, text)
    try:
        await bot.send_message(settings.report_group_id, text)
    except Exception:
        logger.exception('failed to send report group message', extra={'chat_id': chat_id, 'pair_id': pair.id})


async def notify_user(bot: Bot, tg_user_id: int, text: str) -> None:
    try:
        await bot.send_message(tg_user_id, text)
    except Exception:
        logger.exception('failed to notify user', extra={'tg_user_id': tg_user_id})
