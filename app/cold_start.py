"""Cold start orchestration: explicit persona collection + implicit probing.

Runs via SSE with thinking steps, just like normal evaluation.
"""

import json
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Cold start rounds definition
COLD_START_ROUNDS = [
    {
        "round": 1,
        "label": "背景了解",
        "prompt": (
            "你好！我是中文水平评测系统。在开始评测之前，我想先了解一下你的背景：\n"
            "1. 你的母语是什么？\n"
            "2. 你学习中文多久了？\n"
            "3. 你学习中文的主要目的是什么？（比如通过HSK考试、工作交流、兴趣爱好）\n"
            "请简要回答。"
        ),
        "thinking_prompt": "用户正在填写背景信息。分析用户回答中的母语线索和学习背景。",
        "extract": ["native_language", "learning_duration", "learning_goal"],
    },
    {
        "round": 2,
        "label": "场景表达",
        "prompt": (
            "好的，谢谢你的分享。现在我想听你描述一个场景：\n"
            "假设你正在工作场所，请用中文简单描述一下你今天做了什么，或者看到了什么。\n"
            "说几句就可以，不用很长。"
        ),
        "thinking_prompt": "分析用户的句式复杂度、词汇量和表达能力。",
        "extract": ["sentence_complexity", "vocabulary_level"],
    },
    {
        "round": 3,
        "label": "难度探测（基础）",
        "prompt": (
            "很好！接下来我想测试一下你的理解能力。\n"
            "假如现在设备出了故障，同事问你情况，你会怎么用中文向他说明？\n"
            "请尝试用'因为……所以……'的句式来回答。"
        ),
        "thinking_prompt": "评估用户对因果复句的掌握程度，以及专业场景下的语言能力。",
        "extract": ["grammar_usage", "response_time"],
    },
    {
        "round": 4,
        "label": "难度探测（进阶）",
        "prompt": (
            "最后一个问题。\n"
            "如果现在突然下大雨，变压器发出了异常响声，你觉得**由于**天气原因，我们**必须**立刻停止工作吗？\n"
            "请简要说明你的看法。"
        ),
        "thinking_prompt": "通过逻辑连接词和紧急语境下的表达，探测用户语言能力上限。",
        "extract": ["advanced_grammar", "logic_words"],
    },
]

MAX_COLD_START_ROUNDS = 5
MIN_COLD_START_ROUNDS = 3


def _check_cold_start_complete(cold_start_state: dict) -> bool:
    """Check if cold start has gathered enough information to end."""
    collected = cold_start_state.get("collected", set())
    round_num = cold_start_state.get("round", 0)

    # Must complete at least MIN_COLD_START_ROUNDS
    if round_num < MIN_COLD_START_ROUNDS:
        return False

    # Explicit data: native_language + learning_goal
    has_explicit = "native_language" in collected and "learning_goal" in collected

    # Implicit data: at least 2 rounds of answer data
    has_implicit = len(cold_start_state.get("answers", [])) >= 2

    if has_explicit and has_implicit:
        return True

    # Max rounds reached
    if round_num >= MAX_COLD_START_ROUNDS:
        return True

    return False


def _build_initial_vector(cold_start_state: dict) -> dict:
    """Build Initial_Vector from cold start data."""
    answers = cold_start_state.get("answers", [])
    explicit = cold_start_state.get("explicit_data", {})

    # Compute estimated HSK level from answer quality
    estimated_hsk = 2  # default starting point
    if answers:
        avg_len = sum(a.get("answer_length", 0) for a in answers) / len(answers)
        avg_time = sum(a.get("response_time", 10) for a in answers) / len(answers)

        # Longer answers + faster response → higher level
        if avg_len > 30 and avg_time < 10:
            estimated_hsk = 4
        elif avg_len > 15 and avg_time < 15:
            estimated_hsk = 3
        elif avg_len > 5:
            estimated_hsk = 2
        else:
            estimated_hsk = 1

    # Skill levels estimation
    skill_levels = {
        "hsk": round(estimated_hsk / 6 * 100, 1),
        "vocabulary": round(min(estimated_hsk / 6 * 100, 80), 1),
        "grammar": round(min(estimated_hsk / 6 * 100, 75), 1),
        "reading": round(min(estimated_hsk / 6 * 100, 70), 1),
    }

    return {
        "language_family": explicit.get("native_language", "unknown"),
        "domain_knowledge": explicit.get("learning_goal", "general"),
        "initial_difficulty": estimated_hsk,
        "input_stability": "normal",  # will refine with more data
        "skill_levels": skill_levels,
        "hsk_level": estimated_hsk,
        "cold_start_complete": True,
    }


async def _save_cold_start_result(user_id: str, initial_vector: dict, db_session: AsyncSession):
    """Save cold start result to user profile."""
    from models.session import UserProfile

    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db_session.add(profile)
        await db_session.flush()

    profile.hsk_level = initial_vector["hsk_level"]
    profile.skill_levels = initial_vector["skill_levels"]
    if profile.stubborn_errors is None:
        profile.stubborn_errors = []
    if profile.strengths is None:
        profile.strengths = []
    if profile.next_focus is None:
        profile.next_focus = []

    await db_session.commit()
