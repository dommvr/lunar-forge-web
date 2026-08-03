"""Async SQLAlchemy engine/session construction without startup side effects."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_database_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
) -> AsyncEngine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        options.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=300,
        )
    return create_async_engine(database_url, **options)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
