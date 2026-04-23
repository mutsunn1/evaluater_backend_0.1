"""HSK 词表数据库模型。"""

from sqlalchemy import Column, Integer, String

from core.database import Base


class HSKWord(Base):
    __tablename__ = "hsk_words"

    id = Column(Integer, primary_key=True, comment="词汇 ID（对应原始数据 id）")
    level = Column(Integer, nullable=False, index=True, comment="HSK 等级 1-9")
    word = Column(String(50), nullable=False, index=True, comment="词语")
    pinyin = Column(String(100), nullable=True, comment="拼音")
    pos = Column(String(50), nullable=True, comment="词性")

    @staticmethod
    def get_levels():
        return list(range(1, 10))
