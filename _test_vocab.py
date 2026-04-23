"""Test vocabulary services."""
import sys
sys.path.insert(0, '.')

from services.fence_service import _get_word_set, check_words_in_vocabulary, check_question_vocabulary
from services.ttr_engine import compute_ttr, compute_mtld, compute_vocabulary_profile
import asyncio

print(f"HSK 1-3 vocabulary size: {len(_get_word_set(3))}")
print(f"HSK 1-6 vocabulary size: {len(_get_word_set(6))}")

# Test fence check
result = asyncio.run(check_words_in_vocabulary('今天我去学校学习了中文', max_level=3))
print(f"\nFence check (max_level=3):")
print(f"  Known: {result['known_words']}")
print(f"  Unknown: {result['unknown_words']}")
print(f"  Coverage: {result['vocab_coverage']:.1%}")

# Test TTR
text = "因为机器坏了，所以我们不能工作了。因为这个问题很难，所以我们需要找工程师来帮忙。"
ttr = compute_ttr(text)
mtld = compute_mtld(text)
profile = compute_vocabulary_profile(text)
print(f"\nTTR analysis:")
print(f"  TTR: {ttr['ttr']}")
print(f"  Tokens: {ttr['token_count']}, Types: {ttr['type_count']}")
print(f"  MTLD: {mtld['mtld']}")
print(f"  Weighted level: {profile['weighted_level']}")
print(f"  Known rate: {profile['known_rate']}%")
