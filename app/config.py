from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import FrozenSet


def _csv_ints(value: str | None) -> FrozenSet[int]:
    if not value:
        return frozenset()
    result: set[int] = set()
    for item in value.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            raise ValueError(f"Invalid integer in ADMIN_IDS: {item!r}") from None
    return frozenset(result)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: FrozenSet[int]
    report_group_id: int
    database_url: str

    default_pair_limit: int = 10
    default_channel_per_pair_limit: int = 6
    default_language: str = 'en'
    user_limit: int = 0
    log_level: str = 'INFO'
    health_host: str = '0.0.0.0'
    port: int = 10000
    health_path: str = '/healthz'
    post_cache_limit_per_channel: int = 50
    album_collect_delay_seconds: float = 2.0
    banned_silent: bool = True
    admin_contact: str = '@mnsm6003'

    @property
    def sqlalchemy_url(self) -> str:
        """Return an async SQLAlchemy URL that works with Neon/PostgreSQL."""
        url = self.database_url.strip()
        if url.startswith('postgres://'):
            url = 'postgresql://' + url.removeprefix('postgres://')
        if url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        # asyncpg does not accept sslmode=require in the query string.
        # app/db/session.py converts sslmode=require to connect_args={"ssl": "require"}.
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    bot_token = os.getenv('BOT_TOKEN', '').strip()
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not bot_token:
        raise RuntimeError('BOT_TOKEN is required')
    if not database_url:
        raise RuntimeError('DATABASE_URL is required')

    default_language = os.getenv('DEFAULT_LANGUAGE', 'en').strip().lower()
    if default_language not in {'en', 'my'}:
        default_language = 'en'

    return Settings(
        bot_token=bot_token,
        admin_ids=_csv_ints(os.getenv('ADMIN_IDS')),
        report_group_id=_int_env('REPORT_GROUP_ID', -5159311101),
        database_url=database_url,
        default_pair_limit=_int_env('DEFAULT_PAIR_LIMIT', 10),
        default_channel_per_pair_limit=_int_env('DEFAULT_CHANNEL_PER_PAIR_LIMIT', 6),
        default_language=default_language,
        user_limit=_int_env('USER_LIMIT', 0),
        log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        health_host=os.getenv('HEALTH_HOST', '0.0.0.0'),
        port=_int_env('PORT', 10000),
        health_path=os.getenv('HEALTH_PATH', '/healthz'),
        post_cache_limit_per_channel=_int_env('POST_CACHE_LIMIT_PER_CHANNEL', 50),
        album_collect_delay_seconds=_float_env('ALBUM_COLLECT_DELAY_SECONDS', 2.0),
        banned_silent=os.getenv('BANNED_SILENT', 'true').lower() in {'1', 'true', 'yes', 'on'},
        admin_contact=os.getenv('ADMIN_CONTACT', '@mnsm6003'),
    )
