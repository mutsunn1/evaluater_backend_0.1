"""Mock TTR (Type-Token Ratio) calculation engine.

Replace with real TTR computation when available.
"""


async def calculate_ttr(text: str) -> dict:
    return {
        "status": "development",
        "ttr": None,
        "text_length": len(text),
        "message": "TTR 检测模块开发中，当前返回模拟数据。"
                   "词汇多样性（TTR）计算功能等待接入真实的词汇检测程序。",
    }
