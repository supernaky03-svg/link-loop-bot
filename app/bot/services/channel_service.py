from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from app.bot.services.link_service import normalize_channel_input, public_channel_link

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChannelCheckResult:
    ok: bool
    input_value: str
    chat_id: int | None = None
    title: str | None = None
    username: str | None = None
    channel_link: str | None = None
    order_no: int | None = None
    error: str | None = None


async def resolve_and_check_channel(bot: Bot, value: str, order_no: int | None = None) -> ChannelCheckResult:
    normalized = normalize_channel_input(value)
    try:
        chat = await bot.get_chat(normalized)
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
        ok = False
        if isinstance(member, ChatMemberOwner):
            ok = True
        elif isinstance(member, ChatMemberAdministrator):
            ok = bool(getattr(member, 'can_post_messages', False))

        username = chat.username
        title = chat.title or username or str(chat.id)
        return ChannelCheckResult(
            ok=ok,
            input_value=value,
            chat_id=chat.id,
            title=title,
            username=username,
            channel_link=public_channel_link(username, chat.id),
            order_no=order_no,
            error=None if ok else 'missing_admin',
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.info('channel resolve/admin check failed: %s', exc, extra={'channel_input': value})
        return ChannelCheckResult(ok=False, input_value=value, order_no=order_no, error='resolve_failed')
    except Exception:
        logger.exception('unexpected channel check error', extra={'channel_input': value})
        return ChannelCheckResult(ok=False, input_value=value, order_no=order_no, error='unexpected')


def parse_channel_list(raw: str, by_order: bool) -> list[tuple[int | None, str]]:
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    result: list[tuple[int | None, str]] = []
    for idx, part in enumerate(parts, start=1):
        order_no: int | None = None
        link = part
        if by_order and '-' in part:
            maybe_no, maybe_link = part.split('-', 1)
            maybe_no = maybe_no.strip()
            if maybe_no.isdigit() and maybe_link.strip():
                order_no = int(maybe_no)
                link = maybe_link.strip()
        if order_no is None:
            order_no = idx
        result.append((order_no, link.strip()))
    return result
