"""Confidence scoring and adaptive stopping for the evaluation session."""

import math


# Configurable thresholds
MIN_QUESTIONS = 3
MAX_QUESTIONS = 12
CONFIDENCE_WIDTH = 0.15  # 95% CI width threshold (±7.5%)
MIN_ACCURACY_CONSEC = 3  # consecutive correct answers before stop


def compute_confidence(results: list[dict]) -> dict:
    """Compute confidence interval for accuracy rate.

    Uses Wilson score interval for binomial proportion.

    Args:
        results: List of {"is_correct": bool, "score": float|null, "item_id": int}

    Returns:
        {accuracy, ci_lower, ci_upper, confidence, sample_size}
        confidence = 1 - ci_width (how narrow the interval is)
    """
    n = len(results)
    if n == 0:
        return {"accuracy": 0.0, "ci_lower": 0.0, "ci_upper": 1.0, "confidence": 0.0, "sample_size": 0}

    # Objective questions: use is_correct
    objective = [r for r in results if "is_correct" in r]
    if objective:
        k = sum(1 for r in objective if r["is_correct"])
        n_obj = len(objective)
        p = k / n_obj
        # Wilson score interval
        z = 1.96  # 95% CI
        denom = 1 + z**2 / n_obj
        center = (p + z**2 / (2 * n_obj)) / denom
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n_obj)) / n_obj) / denom
        ci_lower = max(0, center - margin)
        ci_upper = min(1, center + margin)
    else:
        # Subjective: use average score
        scores = [r.get("score", 50) for r in results]
        p = sum(scores) / len(scores) / 100
        ci_lower = max(0, p - 0.1)
        ci_upper = min(1, p + 0.1)

    confidence = 1 - (ci_upper - ci_lower)
    return {
        "accuracy": round(p * 100, 1),
        "ci_lower": round(ci_lower * 100, 1),
        "ci_upper": round(ci_upper * 100, 1),
        "confidence": round(confidence, 2),
        "sample_size": n,
    }


def should_stop(results: list[dict], reason: str = "") -> dict | None:
    """Check if evaluation should stop early.

    Returns stop decision dict or None if should continue.
    """
    n = len(results)
    stats = compute_confidence(results)

    # Hard limits
    if n >= MAX_QUESTIONS:
        return {
            "should_stop": True,
            "reason": f"已达到最大题数上限（{MAX_QUESTIONS}题）",
            "confidence": stats["confidence"],
            "accuracy": stats["accuracy"],
        }

    # Minimum questions before any stopping
    if n < MIN_QUESTIONS:
        return None

    # High confidence (narrow CI)
    if stats["confidence"] >= (1 - CONFIDENCE_WIDTH):
        return {
            "should_stop": True,
            "reason": f"评测置信度已达标（{stats['confidence']:.0%}）",
            "confidence": stats["confidence"],
            "accuracy": stats["accuracy"],
        }

    # Consecutive correct answers
    if n >= MIN_ACCURACY_CONSEC + 2:
        recent = results[-(MIN_ACCURACY_CONSEC + 2):]
        if all(r.get("is_correct", False) for r in recent):
            return {
                "should_stop": True,
                "reason": f"连续{MIN_ACCURACY_CONSEC + 2}题全部正确，置信度已饱和",
                "confidence": stats["confidence"],
                "accuracy": stats["accuracy"],
            }

    # Very low consecutive accuracy
    if n >= 5:
        recent = results[-5:]
        if all(not r.get("is_correct", True) for r in recent):
            return {
                "should_stop": True,
                "reason": "连续5题全部错误，已可判定水平",
                "confidence": stats["confidence"],
                "accuracy": stats["accuracy"],
            }

    return None
