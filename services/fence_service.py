"""Mock knowledge fence service. Checks whether words are in the industry vocabulary whitelist/blacklist.

Replace with real word library integration when available.
"""


async def check_words(words: list[str] | str, mode: str = "forbidden") -> dict:
    if isinstance(words, str):
        words = [words]

    return {
        "status": "development",
        "checked_words": words,
        "mode": mode,
        "violations": [],
        "message": "知识围栏服务开发中：当前所有词汇检查均通过（模拟数据）。"
                   "后续将接入行业标准词库进行真实过滤。",
    }


async def get_whitelist() -> dict:
    return {
        "status": "development",
        "message": "行业白名单词库加载开发中。",
    }


async def get_blacklist() -> dict:
    return {
        "status": "development",
        "message": "行业黑名单词库加载开发中。",
    }
