"""
HSK 词表导入脚本

将 hsk_vocabulary/ 下的 JSON 词表数据导入 PostgreSQL 的 hsk_words 表。
支持增量导入（已存在的词不重复插入）。

用法:
    conda activate agent
    python import_vocabulary.py
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from core.database import _get_sync_url
from models.vocabulary import HSKWord

VOCAB_DIR = Path(__file__).parent / "hsk_vocabulary"


def _get_sync_engine():
    url = _get_sync_url(settings.database_url)
    return create_engine(url, echo=False)


def load_level_words(level: str) -> list[dict]:
    """Load words from hsk_level_{level}.json."""
    level_files = {
        "1": "hsk_level_1.json",
        "2": "hsk_level_2.json",
        "3": "hsk_level_3.json",
        "4": "hsk_level_4.json",
        "5": "hsk_level_5.json",
        "6": "hsk_level_6.json",
        "7-9": "hsk_level_7_9.json",
    }
    filename = level_files.get(level)
    if not filename:
        return []
    filepath = VOCAB_DIR / filename
    if not filepath.exists():
        print(f"  Warning: {filepath} not found, skipping level {level}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def import_all():
    engine = _get_sync_engine()

    # Create table
    from core.database import Base
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    levels = ["1", "2", "3", "4", "5", "6", "7-9"]
    total_imported = 0
    total_skipped = 0

    for level in levels:
        words = load_level_words(level)
        if not words:
            continue

        numeric_level = int(level.split("-")[0]) if level != "7-9" else 7

        imported = 0
        skipped = 0
        for w in words:
            # Check if already exists
            existing = session.query(HSKWord).filter_by(id=w["id"]).first()
            if existing:
                skipped += 1
                continue

            session.add(HSKWord(
                id=w["id"],
                level=numeric_level,
                word=w["word"],
                pinyin=w.get("pinyin", ""),
                pos=w.get("pos", ""),
            ))
            imported += 1

        session.commit()
        print(f"  Level {level}: {imported} imported, {skipped} skipped (total: {len(words)})")
        total_imported += imported
        total_skipped += skipped

    session.close()
    engine.dispose()

    print(f"\nImport complete: {total_imported} new, {total_skipped} skipped")


if __name__ == "__main__":
    import_all()
