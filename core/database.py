import asyncio

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

_async_engine = None
_async_session_factory = None
_sync_engine = None

Base = declarative_base()


def _get_sync_url(async_url: str) -> str:
    """Replace asyncpg dialect with pg8000 for DDL operations (pure Python, no C ext issues)."""
    return async_url.replace("+asyncpg", "+pg8000")


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "debug",
            pool_size=10,
            max_overflow=20,
        )
    return _async_engine


def get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            _get_sync_url(settings.database_url),
            echo=False,
        )
    return _sync_engine


async def init_db() -> None:
    from models.session import SessionEvent, UserProfile  # noqa: F401

    def _create_tables():
        Base.metadata.create_all(get_sync_engine())

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _create_tables)


async def shutdown_db() -> None:
    global _async_engine, _sync_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
