from __future__ import annotations

import re

from app.db.models import PairChannel

_USERNAME_RE = re.compile(r'^(?:https?://)?t\.me/([A-Za-z0-9_]{5,})(?:/\d+)?/?$')
_PRIVATE_C_RE = re.compile(r'^(?:https?://)?t\.me/c/(\d+)(?:/\d+)?/?$')
_INVITE_LINK_RE = re.compile(r'^(?:https?://)?t\.me/(?:\+|joinchat/)[A-Za-z0-9_-]+/?$')


def is_private_invite_link(value: str) -> bool:
    """Return True for t.me/+hash or t.me/joinchat/hash links.

    Telegram Bot API methods like getChat/getChatMember cannot resolve a
    private invite hash as chat_id. The bot must be given @username, numeric
    -100... chat ID, or a t.me/c/... link copied from an existing post.
    """
    return bool(_INVITE_LINK_RE.match(value.strip()))


def normalize_channel_input(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value.startswith('@'):
        return value
    if value.lstrip('-').isdigit():
        return value
    m = _USERNAME_RE.match(value)
    if m:
        return '@' + m.group(1)
    m = _PRIVATE_C_RE.match(value)
    if m:
        return '-100' + m.group(1)
    return value


def public_channel_link(username: str | None, chat_id: int | None = None) -> str | None:
    if username:
        return f'https://t.me/{username.lstrip("@")}'
    if chat_id and str(chat_id).startswith('-100'):
        return f'https://t.me/c/{str(chat_id)[4:]}'
    return None


def post_link(chat_id: int, message_id: int, username: str | None = None) -> str:
    if username:
        return f'https://t.me/{username.lstrip("@")}/{message_id}'
    raw = str(chat_id)
    if raw.startswith('-100'):
        return f'https://t.me/c/{raw[4:]}/{message_id}'
    return f'https://t.me/c/{raw.lstrip("-")}/{message_id}'


def channel_link_from_pair_channel(channel: PairChannel) -> str:
    return channel.channel_link or public_channel_link(channel.username, channel.chat_id) or str(channel.chat_id)
