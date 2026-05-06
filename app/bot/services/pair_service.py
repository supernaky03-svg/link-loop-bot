from __future__ import annotations

import random

from app.config import Settings
from app.db.models import Pair, PairChannel, User
from app.db.repository import Repository


def effective_pair_limit(user: User, settings: Settings, repo_default: int | None = None) -> int:
    return user.pair_limit or repo_default or settings.default_pair_limit


def effective_channel_limit(user: User, settings: Settings, repo_default: int | None = None) -> int:
    return user.channel_per_pair_limit or repo_default or settings.default_channel_per_pair_limit


def pair_details(pair: Pair) -> str:
    status = 'Paused' if pair.is_paused else ('Active' if pair.is_active else 'Inactive')
    lines = [
        f'Pair {pair.pair_no}',
        f'Style: {pair.repost_style}',
        f'Movie Rule: {"ON" if pair.movie_rule else "OFF"}',
        f'Status: {status}',
        'Channels:',
    ]
    for ch in sorted(pair.channels, key=lambda c: c.order_no):
        lines.append(f'{ch.order_no}. {ch.title} ({ch.chat_id})')
    return '\n'.join(lines)


def build_route(pair: Pair, source_chat_id: int) -> list[PairChannel]:
    active_channels = [ch for ch in pair.channels if ch.is_active]
    source = next((ch for ch in active_channels if ch.chat_id == source_chat_id), None)
    if not source:
        return []
    others = [ch for ch in active_channels if ch.chat_id != source_chat_id]
    if pair.repost_style == 'by_order':
        others.sort(key=lambda c: (c.order_no, c.id))
    else:
        random.shuffle(others)
    return [source, *others]


async def user_limits(repo: Repository, user: User, settings: Settings) -> tuple[int, int]:
    default_pair = await repo.get_int_setting('default_pair_limit', settings.default_pair_limit)
    default_channel = await repo.get_int_setting(
        'default_channel_per_pair_limit', settings.default_channel_per_pair_limit
    )
    return effective_pair_limit(user, settings, default_pair), effective_channel_limit(
        user, settings, default_channel
    )
