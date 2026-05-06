from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import PairChannel

_USERNAME_RE = re.compile(r'^(?:https?://)?t\.me/([A-Za-z0-9_]{5,})(?:/\d+)?/?$')
_PRIVATE_C_RE = re.compile(r'^(?:https?://)?t\.me/c/(\d+)(?:/\d+)?/?$')
_INVITE_LINK_RE = re.compile(r'^(?:https?://)?t\.me/(?:\+|joinchat/)[A-Za-z0-9_-]+/?$')
_CHANNEL_ID_RE = re.compile(r'^-?100\d{5,}$')
_WRAPPED_RE = re.compile(r'^(.+?)\((.+)\)$')
_VISIBLE_LINK_RE = re.compile(r'(?i)(?:https?://|www\.|t\.me/|telegram\.me/)\S+')


@dataclass(slots=True)
class ParsedChannelInput:
    raw: str
    order_no: int
    chat_id: int | None = None
    username: str | None = None
    public_link: str | None = None
    invite_link: str | None = None
    missing: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ParsedChannelInput':
        return cls(
            raw=str(data.get('raw') or ''),
            order_no=int(data.get('order_no') or 1),
            chat_id=int(data['chat_id']) if data.get('chat_id') is not None else None,
            username=data.get('username'),
            public_link=data.get('public_link'),
            invite_link=data.get('invite_link'),
            missing=data.get('missing'),
            error=data.get('error'),
        )

    @property
    def resolve_value(self) -> str | None:
        if self.username:
            return '@' + self.username.lstrip('@')
        if self.chat_id is not None:
            return str(self.chat_id)
        return None


def _clean(value: str) -> str:
    return value.strip().strip('"\'').strip()


def is_private_invite_link(value: str) -> bool:
    """Return True for t.me/+hash or t.me/joinchat/hash links."""
    return bool(_INVITE_LINK_RE.match(_clean(value)))


def normalize_invite_link(value: str) -> str | None:
    value = _clean(value)
    if not value:
        return None
    if value.startswith('t.me/') or value.startswith('telegram.me/'):
        value = 'https://' + value
    if _INVITE_LINK_RE.match(value):
        return value.rstrip('/')
    return None


def chat_id_from_value(value: str) -> int | None:
    value = _clean(value)
    if _CHANNEL_ID_RE.match(value):
        chat_id = int(value)
        if chat_id > 0:
            chat_id = int('-100' + str(chat_id)[3:]) if str(chat_id).startswith('100') else -chat_id
        return chat_id
    match = _PRIVATE_C_RE.match(value)
    if match:
        return int('-100' + match.group(1))
    return None


def username_from_value(value: str) -> str | None:
    value = _clean(value)
    if value.startswith('@') and len(value) >= 6:
        return value[1:]
    match = _USERNAME_RE.match(value)
    if match:
        return match.group(1)
    return None


def normalize_channel_input(value: str) -> str:
    value = _clean(value)
    if not value:
        return value
    invite = normalize_invite_link(value)
    if invite:
        return invite
    chat_id = chat_id_from_value(value)
    if chat_id is not None:
        return str(chat_id)
    username = username_from_value(value)
    if username:
        return '@' + username
    return value


def _classify(value: str) -> dict:
    value = _clean(value)
    invite_link = normalize_invite_link(value)
    if invite_link:
        return {'kind': 'invite', 'invite_link': invite_link}
    chat_id = chat_id_from_value(value)
    if chat_id is not None:
        return {'kind': 'chat_id', 'chat_id': chat_id}
    username = username_from_value(value)
    if username:
        return {
            'kind': 'public',
            'username': username,
            'public_link': public_channel_link(username, None),
        }
    return {'kind': 'invalid', 'value': value}


def _split_paired_token(token: str) -> list[str]:
    token = _clean(token)
    if '=' in token:
        left, right = token.split('=', 1)
        return [_clean(left), _clean(right)]
    match = _WRAPPED_RE.match(token)
    if match:
        return [_clean(match.group(1)), _clean(match.group(2))]
    return [token]


def parse_channel_input_token(token: str, order_no: int) -> ParsedChannelInput:
    raw = _clean(token)
    pieces = [piece for piece in _split_paired_token(raw) if piece]
    if len(pieces) > 2:
        return ParsedChannelInput(raw=raw, order_no=order_no, error='invalid_channel_input')

    parsed = [_classify(piece) for piece in pieces]
    if any(part['kind'] == 'invalid' for part in parsed):
        return ParsedChannelInput(raw=raw, order_no=order_no, error='invalid_channel_input')

    if len(parsed) == 1:
        part = parsed[0]
        if part['kind'] == 'public':
            return ParsedChannelInput(
                raw=raw,
                order_no=order_no,
                username=part['username'],
                public_link=part['public_link'],
            )
        if part['kind'] == 'invite':
            return ParsedChannelInput(
                raw=raw,
                order_no=order_no,
                invite_link=part['invite_link'],
                missing='chat_id',
            )
        if part['kind'] == 'chat_id':
            return ParsedChannelInput(
                raw=raw,
                order_no=order_no,
                chat_id=part['chat_id'],
                missing='invite_link',
            )

    invite_link: str | None = None
    chat_id: int | None = None
    username: str | None = None
    public_link: str | None = None
    for part in parsed:
        if part['kind'] == 'invite':
            invite_link = part['invite_link']
        elif part['kind'] == 'chat_id':
            chat_id = part['chat_id']
        elif part['kind'] == 'public':
            username = part['username']
            public_link = part['public_link']

    if username and not invite_link and chat_id is None:
        return ParsedChannelInput(raw=raw, order_no=order_no, username=username, public_link=public_link)
    if invite_link and chat_id is not None and not username:
        return ParsedChannelInput(raw=raw, order_no=order_no, chat_id=chat_id, invite_link=invite_link)
    return ParsedChannelInput(raw=raw, order_no=order_no, error='invalid_channel_input')


def parse_order_prefix(part: str, fallback_order: int, by_order: bool) -> tuple[int, str]:
    part = _clean(part)
    if by_order:
        match = re.match(r'^(\d+)\s*-\s*(.+)$', part)
        if match:
            return int(match.group(1)), _clean(match.group(2))
    return fallback_order, part


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


def channel_link_from_pair_channel(channel: 'PairChannel') -> str:
    invite_link = getattr(channel, 'invite_link', None)
    if invite_link:
        return invite_link
    return channel.channel_link or public_channel_link(channel.username, channel.chat_id) or str(channel.chat_id)


def strip_visible_links(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = _VISIBLE_LINK_RE.sub('', text)
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    return cleaned.strip() or None
