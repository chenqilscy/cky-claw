"""性能优化测试 — query_cache / 索引迁移 / 缓存失效。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import query_cache


class TestQueryCache:
    """query_cache 缓存模块测试。"""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetch(self) -> None:
        """缓存未命中时调用 fetch_fn 并写入缓存。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        fetch_fn = AsyncMock(return_value={"key": "value"})

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            result = await query_cache.get_or_fetch("test:key", fetch_fn, ttl=60)

        assert result == {"key": "value"}
        fetch_fn.assert_awaited_once()
        mock_redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetch(self) -> None:
        """缓存命中时跳过 fetch_fn。"""
        cached_data = json.dumps({"cached": True})
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        fetch_fn = AsyncMock()

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            result = await query_cache.get_or_fetch("test:key", fetch_fn)

        assert result == {"cached": True}
        fetch_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_failure_degrades_to_fetch(self) -> None:
        """Redis 不可用时降级为直接查询。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis down"))

        fetch_fn = AsyncMock(return_value={"fallback": True})

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            result = await query_cache.get_or_fetch("test:key", fetch_fn)

        assert result == {"fallback": True}
        fetch_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_deletes_key(self) -> None:
        """invalidate 删除指定缓存。"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            await query_cache.invalidate("test:key")

        mock_redis.delete.assert_awaited_once_with("ckyclaw:qcache:test:key")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_scans_and_deletes(self) -> None:
        """invalidate_pattern 按模式扫描并删除。"""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(
            return_value=(0, ["ckyclaw:qcache:agent:foo", "ckyclaw:qcache:agent:bar"])
        )
        mock_redis.delete = AsyncMock()

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            await query_cache.invalidate_pattern("agent:*")

        mock_redis.scan.assert_awaited_once()
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_redis_failure_no_raise(self) -> None:
        """Redis 失败不抛异常。"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis down"))

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            # 不应抛异常
            await query_cache.invalidate("test:key")

    @pytest.mark.asyncio
    async def test_cache_serializes_datetime(self) -> None:
        """缓存能序列化包含 datetime 的数据（default=str）。"""
        from datetime import datetime

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        data = {"ts": datetime.now(UTC), "count": 42}
        fetch_fn = AsyncMock(return_value=data)

        with patch("app.services.query_cache.get_redis", return_value=mock_redis):
            result = await query_cache.get_or_fetch("test:dt", fetch_fn)

        assert result["count"] == 42
        mock_redis.setex.assert_awaited_once()


class TestMigration0057:
    """验证索引迁移脚本存在且结构正确。"""

    def test_migration_file_exists(self) -> None:
        from pathlib import Path
        migration = Path(__file__).parent.parent / "alembic" / "versions" / "0057_perf_composite_indexes.py"
        assert migration.exists(), f"迁移文件不存在: {migration}"

    def test_migration_has_upgrade_downgrade(self) -> None:
        import importlib.util
        from pathlib import Path

        migration_path = Path(__file__).parent.parent / "alembic" / "versions" / "0057_perf_composite_indexes.py"
        spec = importlib.util.spec_from_file_location("migration_0057", str(migration_path))
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert mod.revision == "0057"
        assert mod.down_revision == "0056"


class TestAgentCacheInvalidation:
    """验证 Agent 变更时缓存失效。"""

    @pytest.mark.asyncio
    async def test_update_agent_invalidates_cache(self) -> None:
        """update_agent 调用后触发缓存失效。"""
        from app.schemas.agent import AgentUpdate
        from app.services.agent import update_agent

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.is_active = True
        mock_agent.is_deleted = False
        mock_agent.id = uuid.uuid4()

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_agent)))
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        update_data = AgentUpdate(description="new desc")

        with (
            patch("app.services.agent.create_version", new_callable=AsyncMock),
            patch("app.services.agent.query_cache") as mock_cache,
        ):
            mock_cache.invalidate = AsyncMock()
            await update_agent(db, "test-agent", update_data)
            mock_cache.invalidate.assert_awaited_once_with("agent:test-agent")

    @pytest.mark.asyncio
    async def test_delete_agent_invalidates_cache(self) -> None:
        """delete_agent 调用后触发缓存失效。"""
        from app.services.agent import delete_agent

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.is_active = True
        mock_agent.is_deleted = False

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_agent)))
        db.commit = AsyncMock()

        with patch("app.services.agent.query_cache") as mock_cache:
            mock_cache.invalidate = AsyncMock()
            await delete_agent(db, "test-agent")
            mock_cache.invalidate.assert_awaited_once_with("agent:test-agent")
