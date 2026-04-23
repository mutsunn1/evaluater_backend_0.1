import uuid

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func

from core.database import Base


class SessionEvent(Base):
    __tablename__ = "session_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True, comment="评测 Session ID")
    item_id = Column(Integer, nullable=True, comment="题目序号，None 表示 Session 级别事件")
    turn_id = Column(Integer, nullable=False, default=0, comment="该题目内的交互轮次，从 0 递增")
    event_type = Column(
        String(30), nullable=False, index=True,
        comment="item_generated | item_rejected | item_pushed | user_interaction | user_answer | sub_question_answered | parallel_analysis | session_end",
    )
    payload = Column(JSON, nullable=False, comment="事件详细内容的 JSON 载荷")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, unique=True, index=True)
    native_language = Column(String(20), nullable=True, default="unknown")
    hsk_level = Column(Integer, nullable=True, default=1, comment="当前 HSK 等级 1-6")
    stubborn_errors = Column(JSON, nullable=True, default=list, comment="顽固语法点列表")
    strengths = Column(JSON, nullable=True, default=list, comment="已掌握的能力项")
    next_focus = Column(JSON, nullable=True, default=list, comment="建议关注的训练方向")
    skill_levels = Column(JSON, nullable=True, default=dict, comment="各维度水平: hsk, vocabulary, grammar, reading")
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
