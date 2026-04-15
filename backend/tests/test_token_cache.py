"""token_cache 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.token_cache import _PREFIX, get_or_fetch


@pytest.fixture()
def mock_redis() -> AsyncMock:
    """创建 mock Redis 客户端。"""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    return r


class TestGetOrFetch:
    """get_or_fetch 测试集。"""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_redis: AsyncMock) -> None:
        """缓存命中时直接返回，不调用 fetch_fn。"""
        mock_redis.get = AsyncMock(return_value="cached_token_123")
        fetch_fn = AsyncMock()

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            result = await get_or_fetch("wecom:corp1", fetch_fn)

        assert result == "cached_token_123"
        fetch_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_miss_fetch_success(self, mock_redis: AsyncMock) -> None:
        """缓存未命中时调用 fetch_fn 并写入缓存。"""
        mock_redis.get = AsyncMock(return_value=None)
        fetch_fn = AsyncMock(return_value="new_token_456")

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            result = await get_or_fetch("wecom:corp1", fetch_fn, ttl=3600)

        assert result == "new_token_456"
        fetch_fn.assert_awaited_once()
        mock_redis.setex.assert_awaited_once_with(
            f"{_PREFIX}wecom:corp1", 3600, "new_token_456"
        )

    @pytest.mark.asyncio
    async def test_cache_miss_fetch_returns_none(self, mock_redis: AsyncMock) -> None:
        """fetch_fn 返回 None 时不写缓存。"""
        mock_redis.get = AsyncMock(return_value=None)
        fetch_fn = AsyncMock(return_value=None)

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            result = await get_or_fetch("wecom:corp1", fetch_fn)

        assert result is None
        mock_redis.setex.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_read_failure_degrades(self, mock_redis: AsyncMock) -> None:
        """Redis 读取异常时降级为直接获取。"""
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        fetch_fn = AsyncMock(return_value="fallback_token")

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            result = await get_or_fetch("wecom:corp1", fetch_fn)

        assert result == "fallback_token"
        fetch_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_write_failure_still_returns(self, mock_redis: AsyncMock) -> None:
        """Redis 写入异常时仍返回 token（不影响功能）。"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis down"))
        fetch_fn = AsyncMock(return_value="token_ok")

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            result = await get_or_fetch("feishu:app1", fetch_fn)

        assert result == "token_ok"

    @pytest.mark.asyncio
    async def test_default_ttl(self, mock_redis: AsyncMock) -> None:
        """未指定 TTL 时使用默认 7000 秒。"""
        mock_redis.get = AsyncMock(return_value=None)
        fetch_fn = AsyncMock(return_value="token_x")

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            await get_or_fetch("wechat:app2", fetch_fn)

        mock_redis.setex.assert_awaited_once_with(
            f"{_PREFIX}wechat:app2", 7000, "token_x"
        )

    @pytest.mark.asyncio
    async def test_key_prefix(self, mock_redis: AsyncMock) -> None:
        """缓存 key 使用正确前缀。"""
        mock_redis.get = AsyncMock(return_value="tk")

        with patch("app.services.token_cache.get_redis", return_value=mock_redis):
            await get_or_fetch("test:id1", AsyncMock())

        mock_redis.get.assert_awaited_once_with(f"{_PREFIX}test:id1")
