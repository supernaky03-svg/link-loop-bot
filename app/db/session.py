from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base


def _prepare_url_and_connect_args(url: str) -> tuple[str, dict]:
    """Move sslmode=require from URL query to asyncpg connect_args."""
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


async def close_db() -> None:
    await engine.dispose()
