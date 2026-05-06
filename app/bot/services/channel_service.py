from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from app.bot.services.link_service import (
    ParsedChannelInput,
    parse_channel_input_token,
    parse_order_prefix,
    public_channel_link,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChannelCheckResult:
    ok: bool
    input_value: str
    chat_id: int | None = None
    title: str | None = None
    username: str | None = None
    channel_link: str | None = None
    invite_link: str | None = None
    order_no: int | None = None
    error: str | None = None


@dataclass(slots=True)
class ChannelValidationResult:
    ok: bool
    channels: list[dict]
    error_text: str | None = None
    can_recheck: bool = False
    needs_more_info: bool = False
    parsed_inputs: list[ParsedChannelInput] | None = None


async def resolve_and_check_channel(
    bot: Bot,
    channel_input: ParsedChannelInput | str,
    order_no: int | None = None,
) -> ChannelCheckResult:
    if isinstance(channel_input, str):
        parsed = parse_channel_input_token(channel_input, order_no or 1)
    else:
        parsed = channel_input

    if parsed.error:
        return ChannelCheckResult(
            ok=False,
            input_value=parsed.raw,
            order_no=parsed.order_no,
            error=parsed.error,
        )
    if parsed.missing:
        return ChannelCheckResult(
            ok=False,
            input_value=parsed.raw,
            chat_id=parsed.chat_id,
            invite_link=parsed.invite_link,
            order_no=parsed.order_no,
            error=f'missing_{parsed.missing}',
        )

    resolve_value = parsed.resolve_value
    if not resolve_value:
        return ChannelCheckResult(
            ok=False,
            input_value=parsed.raw,
            order_no=parsed.order_no,
            error='invalid_channel_input',
        )

    try:
        chat = await bot.get_chat(resolve_value)
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
            input_value=parsed.raw,
            chat_id=chat.id,
            title=title,
            username=username,
            channel_link=public_channel_link(username, chat.id),
            invite_link=parsed.invite_link,
            order_no=parsed.order_no,
            error=None if ok else 'missing_admin',
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.info('channel resolve/admin check failed: %s', exc, extra={'channel_input': parsed.raw})
        return ChannelCheckResult(ok=False, input_value=parsed.raw, order_no=parsed.order_no, error='resolve_failed')
    except Exception:
        logger.exception('unexpected channel check error', extra={'channel_input': parsed.raw})
        return ChannelCheckResult(ok=False, input_value=parsed.raw, order_no=parsed.order_no, error='unexpected')


def parse_channel_list(raw: str, by_order: bool) -> list[ParsedChannelInput]:
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    result: list[ParsedChannelInput] = []
    for idx, part in enumerate(parts, start=1):
        order_no, token = parse_order_prefix(part, idx, by_order)
        result.append(parse_channel_input_token(token, order_no))
    return result


def merge_missing_channel_info(
    original_inputs: list[ParsedChannelInput],
    reply_raw: str,
) -> tuple[list[ParsedChannelInput], bool]:
    """Merge user replies into parsed channel inputs that lacked id/link.

    Accepted replies:
    - full mapping: https://t.me/+invite(-100123...)
    - full mapping: -100123...(https://t.me/+invite)
    - full mapping: https://t.me/+invite = -100123...
    - when only one item is missing: user may send just the missing ID or link
    """
    additions = parse_channel_list(reply_raw, by_order=False)
    changed = False
    missing_inputs = [item for item in original_inputs if item.missing]

    # One missing item shortcut: user can reply with only the missing value.
    if len(missing_inputs) == 1 and len(additions) == 1:
        target = missing_inputs[0]
        addition = additions[0]
        if target.missing == 'chat_id' and addition.chat_id is not None:
            target.chat_id = addition.chat_id
            target.missing = None if target.invite_link else 'invite_link'
            changed = True
        elif target.missing == 'invite_link' and addition.invite_link:
            target.invite_link = addition.invite_link
            target.missing = None if target.chat_id is not None else 'chat_id'
            changed = True

    for target in missing_inputs:
        if target.missing == 'chat_id' and target.invite_link:
            for addition in additions:
                if addition.invite_link == target.invite_link and addition.chat_id is not None:
                    target.chat_id = addition.chat_id
                    target.missing = None
                    changed = True
                    break
        elif target.missing == 'invite_link' and target.chat_id is not None:
            for addition in additions:
                if addition.chat_id == target.chat_id and addition.invite_link:
                    target.invite_link = addition.invite_link
                    target.missing = None
                    changed = True
                    break
    return original_inputs, changed
