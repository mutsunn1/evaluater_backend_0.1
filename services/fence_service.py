"""基于 HSK 词库的知识围栏服务。

提供渐进式披露的词库过滤和词汇检查能力：
- 检查某个词是否在指定 HSK 等级及以下（是否超纲）
- 获取某等级及以下的所有词汇集合（用于出题约束）
- 检查文本中所有词的等级分布
"""

import re
from functools import lru_cache

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models.vocabulary import HSKWord


# ---------- 同步缓存（用于出题 prompt 构建等快速查询） ----------

def _get_sync_engine():
    from sqlalchemy import create_engine
    from app.config import settings
    from core.database import _get_sync_url
    return create_engine(_get_sync_url(settings.database_url), echo=False)


@lru_cache(maxsize=1)
def _get_all_words(level: int = 0) -> list[tuple[str, int]]:
    """Cached lookup: list of (word, level). level=0 means all levels."""
    engine = _get_sync_engine()
    with engine.connect() as conn:
        query = select(HSKWord.word, HSKWord.level)
        if level > 0:
            query = query.where(HSKWord.level <= level)
        rows = conn.execute(query).fetchall()
        return [(r[0], r[1]) for r in rows]


@lru_cache(maxsize=1)
def _get_word_set(level: int = 0) -> set[str]:
    """Cached set of words at or below given level. level=0 means all levels."""
    words = _get_all_words(level)
    return {w[0] for w in words}


@lru_cache(maxsize=12)
def _get_level_word_set(level: int) -> set[str]:
    """Cached set of words exactly at given level."""
    engine = _get_sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            select(HSKWord.word).where(HSKWord.level == level)
        ).fetchall()
        return {r[0] for r in rows}


async def check_words_in_vocabulary(text: str, max_level: int = 99) -> dict:
    """检查文本中的词是否超纲（超出 max_level 等级）。

    策略：从文本中提取所有可能的词（最长匹配优先），
    检查是否有词不在 max_level 及以下的词库中。

    Args:
        text: 待检查的中文文本
        max_level: 最大允许的 HSK 等级（1-9）

    Returns:
        {
            "violations": [{"word": "...", "is_known": false}],
            "known_words": ["词1", "词2", ...],
            "unknown_words": ["词1", "词2", ...],
            "vocab_coverage": 0.85,  # 词库覆盖率
            "max_level": 3
        }
    """
    if not text or not text.strip():
        return {
            "violations": [],
            "known_words": [],
            "unknown_words": [],
            "vocab_coverage": 1.0,
            "max_level": max_level,
        }

    vocab = _get_word_set(max_level)
    all_vocab = _get_all_words(0)

    # Extract meaningful tokens: split by non-Chinese chars
    chars = re.findall(r'[一-鿿]+', text)

    # Find words using longest-match greedy segmentation
    known = []
    unknown_chars = []
    i = 0
    text_flat = "".join(chars)

    while i < len(text_flat):
        matched = False
        # Try longest match first (up to 6 chars)
        for length in range(min(6, len(text_flat) - i), 0, -1):
            candidate = text_flat[i:i + length]
            if candidate in vocab:
                known.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            unknown_chars.append(text_flat[i])
            i += 1

    return {
        "violations": [{"word": w, "is_known": False} for w in unknown_chars],
        "known_words": known,
        "unknown_words": list(set(unknown_chars)),
        "vocab_coverage": len(known) / max(len(text_flat), 1),
        "max_level": max_level,
    }


async def get_vocabulary_for_level(level: int) -> dict:
    """获取指定 HSK 等级及以下的词汇统计信息。

    用于出题 Agent 的渐进式披露——只暴露当前等级及以下的词汇。

    Args:
        level: HSK 等级 (1-9)

    Returns:
        {
            "level": 3,
            "word_count": 1000,
            "cumulative_count": 1500,  # 包含之前所有等级
            "sample_words": ["词1", "词2", ...]  # 随机 20 个示例
        }
    """
    level_set = _get_level_word_set(level)
    cumulative_set = _get_word_set(level)

    import random
    sample = random.sample(list(cumulative_set), min(20, len(cumulative_set)))

    return {
        "level": level,
        "word_count": len(level_set),
        "cumulative_count": len(cumulative_set),
        "sample_words": sample,
    }


async def check_question_vocabulary(question_text: str, user_hsk_level: int) -> dict:
    """检查题目词汇是否在用户当前水平范围内（渐进式披露检查）。

    核心逻辑：题目中不应出现高于用户 HSK 等级 2 级以上的生词。
    例如 HSK 3 的用户，题目可以有 HSK 4 词汇（合理挑战），但不应该有 HSK 6+ 的生词。

    Args:
        question_text: 题目文本
        user_hsk_level: 用户当前 HSK 等级

    Returns:
        {
            "pass": true/false,
            "out_of_level_words": ["超纲词1", ...],
            "max_word_level_found": 3,
            "recommendation": "题目词汇难度适当"
        }
    """
    allowed_level = min(user_hsk_level + 2, 9)  # 最多高 2 级
    result = await check_words_in_vocabulary(question_text, max_level=allowed_level)

    out_of_level = result.get("unknown_words", [])

    return {
        "pass": len(out_of_level) <= 2,  # 允许最多 2 个超纲字/词
        "out_of_level_words": out_of_level,
        "max_word_level_found": allowed_level,
        "vocab_coverage": result.get("vocab_coverage", 0),
        "recommendation": (
            "题目词汇难度适当" if len(out_of_level) <= 2
            else f"题目包含 {len(out_of_level)} 个超纲词，建议替换"
        ),
    }
