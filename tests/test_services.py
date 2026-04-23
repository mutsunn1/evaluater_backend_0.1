"""Tests for mock services: fence_service and ttr_engine."""

import pytest


@pytest.mark.asyncio
class TestFenceService:
    """Test the knowledge fence service mock."""

    async def test_check_words_list(self):
        from services.fence_service import check_words

        result = await check_words(["短路", "跳闸"], mode="forbidden")
        assert result["status"] == "development"
        assert result["checked_words"] == ["短路", "跳闸"]
        assert result["violations"] == []
        assert "开发中" in result["message"]

    async def test_check_words_string(self):
        from services.fence_service import check_words

        result = await check_words("排查", mode="whitelist")
        assert result["checked_words"] == ["排查"]
        assert result["mode"] == "whitelist"

    async def test_get_whitelist(self):
        from services.fence_service import get_whitelist

        result = await get_whitelist()
        assert result["status"] == "development"
        assert "白名单" in result["message"]

    async def test_get_blacklist(self):
        from services.fence_service import get_blacklist

        result = await get_blacklist()
        assert result["status"] == "development"
        assert "黑名单" in result["message"]


@pytest.mark.asyncio
class TestTTREngine:
    """Test the TTR calculation engine mock."""

    async def test_calculate_ttr_returns_development_status(self):
        from services.ttr_engine import calculate_ttr

        result = await calculate_ttr("昨天我把故障设备排查了一遍")
        assert result["status"] == "development"
        assert result["ttr"] is None
        assert result["text_length"] == 13
        assert "开发中" in result["message"]

    async def test_calculate_ttr_empty_text(self):
        from services.ttr_engine import calculate_ttr

        result = await calculate_ttr("")
        assert result["text_length"] == 0

    async def test_calculate_ttr_long_text(self):
        from services.ttr_engine import calculate_ttr

        text = "电力系统中，变压器是核心设备之一。当变压器发生故障时，需要立即启动应急预案。"
        result = await calculate_ttr(text)
        assert result["text_length"] == len(text)
