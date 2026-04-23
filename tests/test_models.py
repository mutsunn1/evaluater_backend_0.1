"""Tests for SQLAlchemy models in models/session.py."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
class TestSessionEventModel:
    """Verify SessionEvent model schema and CRUD."""

    async def test_create_session_event(self, db_session):
        from models.session import SessionEvent

        event = SessionEvent(
            session_id="test-session-1",
            item_id=1,
            turn_id=0,
            event_type="item_generated",
            payload={
                "description": "出题Agent生成的题目元信息",
                "item_data": {"question_type": "multiple_choice", "scene": "电力故障汇报"},
                "qa_status": "pass",
                "retry_count": 0,
            },
        )
        db_session.add(event)
        await db_session.flush()

        assert event.id is not None
        assert event.session_id == "test-session-1"
        assert event.item_id == 1
        assert event.turn_id == 0
        assert event.event_type == "item_generated"
        assert event.payload["item_data"]["question_type"] == "multiple_choice"
        assert event.created_at is not None

    async def test_query_events_by_session_id(self, db_session):
        from models.session import SessionEvent

        for i in range(3):
            db_session.add(SessionEvent(
                session_id="session-query-test",
                item_id=i + 1,
                turn_id=0,
                event_type="item_generated",
                payload={"description": f"Event {i}"},
            ))
        await db_session.flush()

        result = await db_session.execute(
            select(SessionEvent).where(SessionEvent.session_id == "session-query-test")
        )
        events = result.scalars().all()
        assert len(events) == 3

    async def test_item_id_nullable(self, db_session):
        from models.session import SessionEvent

        event = SessionEvent(
            session_id="session-1",
            item_id=None,
            turn_id=0,
            event_type="session_end",
            payload={"description": "Session 结束的总结记录"},
        )
        db_session.add(event)
        await db_session.flush()
        assert event.item_id is None

    async def test_payload_jsonb_serialization(self, db_session):
        from models.session import SessionEvent

        payload = {
            "description": "并行分析的综合结果",
            "user_observer": {"psychological_label": "行业知识不足导致犹豫"},
            "grading": {
                "dimensions": {
                    "character": {"score": 9, "max": 10},
                    "vocabulary": {"score": 7, "max": 10},
                    "sentence": {"score": 8, "max": 10},
                    "pragmatics": {"score": 6, "max": 10},
                },
                "total_score": 30,
            },
            "memory_mgmt": {"actions": []},
        }

        event = SessionEvent(
            session_id="json-test",
            item_id=1,
            turn_id=0,
            event_type="parallel_analysis",
            payload=payload,
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(SessionEvent).where(SessionEvent.id == event.id)
        )
        loaded = result.scalars().first()
        assert loaded.payload["grading"]["total_score"] == 30
        assert loaded.payload["user_observer"]["psychological_label"] == "行业知识不足导致犹豫"


@pytest.mark.asyncio
class TestUserProfileModel:
    """Verify UserProfile model schema and CRUD."""

    async def test_create_profile(self, db_session):
        from models.session import UserProfile

        profile = UserProfile(
            user_id="user-001",
            native_language="en",
            hsk_level=3,
            stubborn_errors=["把字句", "被字句"],
            strengths=["基础词汇", "简单句"],
            next_focus=["衔接词", "行业词汇"],
        )
        db_session.add(profile)
        await db_session.flush()

        assert profile.id is not None
        assert profile.hsk_level == 3
        assert "把字句" in profile.stubborn_errors

    async def test_unique_user_id(self, db_session):
        from models.session import UserProfile
        from sqlalchemy.exc import IntegrityError

        db_session.add(UserProfile(user_id="unique-user", hsk_level=1))
        await db_session.flush()

        db_session.add(UserProfile(user_id="unique-user", hsk_level=2))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_default_values(self, db_session):
        from models.session import UserProfile

        profile = UserProfile(user_id="defaults-user")
        db_session.add(profile)
        await db_session.flush()

        assert profile.native_language == "unknown"
        assert profile.hsk_level == 1
        assert profile.stubborn_errors == []
        assert profile.strengths == []
        assert profile.next_focus == []
