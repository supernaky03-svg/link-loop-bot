from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base


def _prepare_url_and_connect_args(url: str) -> tuple[str, dict]:
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    connect_args: dict = {}
    sslmode = query.pop('sslmode', None)
    if sslmode in {'require', 'verify-ca', 'verify-full'}:
        connect_args['ssl'] = 'require'
    cleaned_query = urlencode(query)
    cleaned_url = urlunsplit((split.scheme, split.netloc, split.path, cleaned_query, split.fragment))
    return cleaned_url, connect_args


settings = get_settings()
DATABASE_URL, CONNECT_ARGS = _prepare_url_and_connect_args(settings.sqlalchemy_url)

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=CONNECT_ARGS,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text('ALTER TABLE IF EXISTS pair_channels ADD COLUMN IF NOT EXISTS invite_link TEXT'))
        # Existing deployments need additive columns and the old loop-step constraint replaced.
        await conn.execute(text('ALTER TABLE IF EXISTS post_items ADD COLUMN IF NOT EXISTS entities JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS post_items ADD COLUMN IF NOT EXISTS caption_entities JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS post_items ADD COLUMN IF NOT EXISTS reply_markup JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_states ADD COLUMN IF NOT EXISTS selected_unit_ids JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_states ADD COLUMN IF NOT EXISTS created_message_ids JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_states ADD COLUMN IF NOT EXISTS footer_message_ids JSONB'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_states ADD COLUMN IF NOT EXISTS footer_ready_at TIMESTAMPTZ'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_events DROP CONSTRAINT IF EXISTS uq_loop_step'))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_events DROP CONSTRAINT IF EXISTS uq_loop_step_v2'))
        await conn.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_loop_step_v2_idx '
            'ON loop_events(loop_id, from_chat_id, from_message_id, to_chat_id, to_message_id)'
        ))
        await conn.execute(text(
            'DELETE FROM loop_states old USING loop_states newer '
            'WHERE old.id < newer.id '
            'AND old.pair_id = newer.pair_id '
            'AND old.origin_chat_id = newer.origin_chat_id '
            'AND old.origin_message_id = newer.origin_message_id'
        ))
        await conn.execute(text('ALTER TABLE IF EXISTS loop_states DROP CONSTRAINT IF EXISTS uq_loop_origin'))
        await conn.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_loop_origin_idx '
            'ON loop_states(pair_id, origin_chat_id, origin_message_id)'
        ))


async def close_db() -> None:
    await engine.dispose()
