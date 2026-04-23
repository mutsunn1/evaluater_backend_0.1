"""User profile skill level assessment.

Runs asynchronously in background — zero impact on response latency.
"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models.session import UserProfile

# Difficulty weights per HSK level
LEVEL_WEIGHTS = {
    "HSK 3": 3,
    "HSK 4": 4,
    "HSK 5": 5,
    "HSK 6": 6,
}

# Grammar point to skill mapping
GRAMMAR_SKILLS = {
    "把字句": "grammar",
    "被字句": "grammar",
    "比较句": "grammar",
    "条件句": "grammar",
    "因果复句": "reading",
    "时间顺序": "reading",
}


def _compute_skill_levels(history: list[dict], answers: list[dict]) -> dict:
    """Compute 4-dimension skill levels from session history + answers.

    Returns: {hsk: float, vocabulary: float, grammar: float, reading: float}
    Each value is 0-100.
    """
    if not history or not answers:
        return {"hsk": 0, "vocabulary": 0, "grammar": 0, "reading": 0}

    # Build answer lookup by item index
    answer_map = {}
    for a in answers:
        item_id = a.get("item_id", 0)
        if item_id:
            answer_map[item_id] = a

    # Aggregate by skill dimension
    skill_scores: dict[str, list[tuple[float, float]]] = {
        "grammar": [],
        "vocabulary": [],
        "reading": [],
    }

    total_weight = 0
    total_correct = 0

    for i, q in enumerate(history):
        item_id = i + 1
        q_level = LEVEL_WEIGHTS.get(q.get("target_level", "HSK 3"), 3)
        weight = q_level / 3.0  # normalize: HSK3=1.0, HSK6=2.0

        a = answer_map.get(item_id, {})
        is_correct = a.get("is_correct", False)
        total_weight += weight
        if is_correct:
            total_correct += weight

        # Map to skill dimensions
        grammar_focus = q.get("grammar_focus", "")
        skill = GRAMMAR_SKILLS.get(grammar_focus, "vocabulary")

        if skill in skill_scores:
            skill_scores[skill].append((weight, 1.0 if is_correct else 0.0))

    # Overall HSK estimation
    accuracy = total_correct / total_weight if total_weight > 0 else 0
    estimated_hsk = 1 + accuracy * 5  # map 0-1 → HSK 1-6

    # Per-skill scores
    result = {"hsk": round(estimated_hsk, 1)}
    for skill, scores in skill_scores.items():
        if scores:
            w = sum(s[0] * s[1] for s in scores)
            t = sum(s[0] for s in scores)
            result[skill] = round((w / t) * 100 if t > 0 else 0, 1)
        else:
            result[skill] = 0

    return result


async def _update_user_profile_async(user_id: str, history: list[dict], answers: list[dict]):
    """Background task: update user profile skill levels. Non-blocking."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalars().first()
            if not profile:
                profile = UserProfile(user_id=user_id)
                session.add(profile)
                await session.flush()

            # Compute skill levels
            skills = _compute_skill_levels(history, answers)
            if profile.skill_levels is None:
                profile.skill_levels = {}
            profile.skill_levels.update(skills)

            # Update HSK level if significantly changed
            new_hsk = int(round(skills["hsk"]))
            if new_hsk != profile.hsk_level and 1 <= new_hsk <= 6:
                profile.hsk_level = new_hsk

            await session.commit()
    except Exception:
        pass  # Silently fail — this is a background task
