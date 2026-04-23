import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add project root to path so imports resolve
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest_asyncio.fixture
async def db_engine():
    """SQLite engine for testing — avoids needing real PostgreSQL."""
    engine = create_async_engine("sqlite+aiosqlite:///./test_evaluator.db", echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yields an AsyncSession bound to the SQLite engine."""
    from core.database import Base
    from models.session import SessionEvent, UserProfile  # noqa: register models

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app():
    """Build a FastAPI app with our session_router but without starting uvicorn."""
    import app.main as main_mod

    app = FastAPI()
    app.include_router(main_mod.session_router)
    return app


@pytest_asyncio.fixture
async def client(app, db_engine):
    """Async HTTP client pointing at the test app, with mocked MAS."""
    import app.main as main_mod

    # Mock the MAS instance so routes don't crash
    mock_mas = AsyncMock()
    mock_mas.call = AsyncMock(return_value={"status": "ok", "data": "mocked"})
    main_mod._mas_instance = mock_mas

    # Override the get_db dependency to use our test session
    from core.database import Base

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[main_mod.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    main_mod._mas_instance = None

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
