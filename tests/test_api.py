"""Integration tests for API routes using httpx + mocked MAS."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def _build_client(app, db_engine, mas_mock):
    """Helper to build a test client with MAS mock and DB override."""
    import app.main as main_mod
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

    main_mod._mas_instance = mas_mock
    app.dependency_overrides[main_mod.get_db] = override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client


async def _cleanup(app, db_engine):
    import app.main as main_mod
    from core.database import Base

    app.dependency_overrides.clear()
    main_mod._mas_instance = None

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
class TestCreateSession:

    async def test_create_session_new_user(self, app, db_engine):
        from unittest.mock import AsyncMock
        mas_mock = AsyncMock()
        client = await _build_client(app, db_engine, mas_mock)

        resp = await client.post("/api/v1/sessions", params={"user_id": "new-user-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["user_id"] == "new-user-001"
        assert "hsk_level" in data

        await _cleanup(app, db_engine)

    async def test_create_session_existing_user(self, app, db_engine):
        from unittest.mock import AsyncMock
        from models.session import UserProfile

        mas_mock = AsyncMock()
        client = await _build_client(app, db_engine, mas_mock)

        # Create existing user
        from core.database import Base
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            s.add(UserProfile(user_id="existing-user", hsk_level=4, native_language="zh"))
            await s.commit()

        resp = await client.post("/api/v1/sessions", params={"user_id": "existing-user"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["hsk_level"] == 4

        await _cleanup(app, db_engine)


@pytest.mark.asyncio
class TestSessionEvents:

    async def test_get_events_empty(self, app, db_engine):
        from unittest.mock import AsyncMock
        mas_mock = AsyncMock()
        client = await _build_client(app, db_engine, mas_mock)

        resp = await client.get("/api/v1/sessions/nonexistent/events")
        assert resp.status_code == 200
        assert resp.json() == []

        await _cleanup(app, db_engine)

    async def test_get_events_returns_data(self, app, db_engine):
        from unittest.mock import AsyncMock
        from models.session import SessionEvent

        mas_mock = AsyncMock()
        client = await _build_client(app, db_engine, mas_mock)

        from core.database import Base
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            s.add(SessionEvent(
                session_id="evt-session",
                item_id=1,
                turn_id=0,
                event_type="item_generated",
                payload={"description": "题目生成事件"},
            ))
            await s.commit()

        resp = await client.get("/api/v1/sessions/evt-session/events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "item_generated"
        assert data[0]["item_id"] == 1
        assert "created_at" in data[0]

        await _cleanup(app, db_engine)


@pytest.mark.asyncio
class TestSessionSummary:

    async def test_summary_filters_events(self, app, db_engine):
        from unittest.mock import AsyncMock
        from models.session import SessionEvent

        mas_mock = AsyncMock()
        client = await _build_client(app, db_engine, mas_mock)

        from core.database import Base
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            # Should be included
            s.add(SessionEvent(
                session_id="sum-session", item_id=1, turn_id=0,
                event_type="item_generated",
                payload={"description": "生成事件"},
            ))
            s.add(SessionEvent(
                session_id="sum-session", item_id=1, turn_id=1,
                event_type="user_answer",
                payload={"description": "用户作答"},
            ))
            # Should be filtered OUT
            s.add(SessionEvent(
                session_id="sum-session", item_id=1, turn_id=2,
                event_type="item_pushed",
                payload={"description": "推送事件"},
            ))
            await s.commit()

        resp = await client.get("/api/v1/sessions/sum-session/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # Only item_generated and user_answer
        assert all(e["event_type"] != "item_pushed" for e in data)

        await _cleanup(app, db_engine)


@pytest.mark.asyncio
class TestMASRoutes:

    async def test_question_mas_not_initialized(self, app, db_engine):
        import app.main as main_mod
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

        main_mod._mas_instance = None  # Simulate not initialized
        app.dependency_overrides[main_mod.get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/v1/sessions/test-1/question")
            assert resp.status_code == 503
            assert "MAS not initialized" in resp.json()["detail"]

        app.dependency_overrides.clear()
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def test_answer_mas_not_initialized(self, app, db_engine):
        import app.main as main_mod
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

        main_mod._mas_instance = None
        app.dependency_overrides[main_mod.get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/sessions/test-1/answer", params={"prompt": "test"})
            assert resp.status_code == 503

        app.dependency_overrides.clear()
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def test_end_session_mas_not_initialized(self, app, db_engine):
        import app.main as main_mod
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

        main_mod._mas_instance = None
        app.dependency_overrides[main_mod.get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/sessions/test-1/end")
            assert resp.status_code == 503

        app.dependency_overrides.clear()
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
