"""基于 HSK 词库的 TTR（词汇多样性）计算引擎。

利用已导入的 HSK 词库对中文文本进行分词，
计算标准化的 Type-Token Ratio，考虑词频和等级分布。
"""

import re
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models.vocabulary import HSKWord


# ---------- 分词（基于 HSK 词库的最长匹配正向分词） ----------

@lru_cache(maxsize=1)
def _get_dict() -> dict[str, int]:
    """Load entire vocabulary as {word: level} for tokenization."""
    from services.fence_service import _get_all_words
    return {w: lv for w, lv in _get_all_words(0)}


def tokenize(text: str) -> list[str]:
    """基于 HSK 词库的最长匹配正向分词。

    策略：从左到右扫描文本，优先匹配最长词（最多 6 字），
    未匹配的单字单独成词。
    """
    text = re.sub(r'[^一-鿿]', '', text)  # 只保留汉字
    words = []
    i = 0
    while i < len(text):
        matched = False
        for length in range(min(6, len(text) - i), 0, -1):
            candidate = text[i:i + length]
            if candidate in _get_dict():
                words.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            words.append(text[i])
            i += 1
    return words


# ---------- TTR 计算 ----------

def compute_ttr(text: str) -> dict:
    """计算标准 TTR（Type-Token Ratio）。

    TTR = 不同词数 / 总词数
    值越接近 1 表示词汇越丰富，越接近 0 表示重复越多。
    """
    tokens = tokenize(text)
    if not tokens:
        return {
            "ttr": 0.0,
            "type_count": 0,
            "token_count": 0,
            "tokens": [],
            "message": "文本中未找到有效词汇",
        }

    types = set(tokens)
    ttr = len(types) / len(tokens)

    return {
        "ttr": round(ttr, 4),
        "type_count": len(types),
        "token_count": len(tokens),
        "tokens": tokens,
        "message": "计算完成",
    }


def compute_mtld(text: str, threshold: float = 0.72) -> dict:
    """计算 MTLD（Moving Average Type-Token Ratio），
    比标准 TTR 更稳定，不受文本长度影响。

    策略：从左到右累加 token，每当 TTR 降至 threshold 以下时
    开始新的 segment，最终取 segments 的平均 TTR。
    """
    tokens = tokenize(text)
    if not tokens:
        return {"mtld": 0.0, "segments": 0, "token_count": 0}

    segments = []
    current_types: set[str] = set()
    current_tokens = 0

    for token in tokens:
        current_types.add(token)
        current_tokens += 1
        current_ttr = len(current_types) / current_tokens

        if current_ttr <= threshold:
            segments.append(current_ttr)
            current_types = set()
            current_tokens = 0

    # Handle remaining tokens
    if current_tokens > 0:
        remaining_ratio = len(current_types) / current_tokens if current_tokens else 0
        # Estimate partial segment contribution
        if remaining_ratio > threshold:
            segments.append((1 - threshold) / (1 - remaining_ratio))

    mtld = sum(segments) / max(len(segments), 1) if segments else 0

    return {
        "mtld": round(mtld, 4),
        "segments": len(segments),
        "token_count": len(tokens),
        "message": "MTLD 计算完成",
    }


def compute_vocabulary_profile(text: str) -> dict:
    """计算文本的词汇等级分布。

    统计文本中各 HSK 等级词汇的数量占比，
    用于评估文本的难度级别。
    """
    tokens = tokenize(text)
    vocab = _get_dict()

    level_counts: dict[int, int] = {}
    known = 0
    unknown = 0

    for token in tokens:
        if token in vocab:
            lv = vocab[token]
            level_counts[lv] = level_counts.get(lv, 0) + 1
            known += 1
        else:
            unknown += 1

    total = max(len(tokens), 1)

    level_profile = {}
    for lv in sorted(level_counts.keys()):
        level_profile[lv] = {
            "count": level_counts[lv],
            "percentage": round(level_counts[lv] / total * 100, 1),
        }

    # Estimate overall difficulty
    if level_counts:
        weighted_level = sum(lv * cnt for lv, cnt in level_counts.items()) / max(known, 1)
    else:
        weighted_level = 0

    return {
        "level_profile": level_profile,
        "known_rate": round(known / total * 100, 1),
        "unknown_rate": round(unknown / total * 100, 1),
        "weighted_level": round(weighted_level, 1),
        "token_count": len(tokens),
        "message": "词汇等级分析完成",
    }
