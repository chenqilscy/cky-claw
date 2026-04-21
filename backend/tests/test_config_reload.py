"""Config cache + reload API 测试。"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.cache import ConfigCache, config_cache, make_cache_key, make_list_cache_key
from app.core.database import get_db as get_db_original
from app.core.deps import get_current_user
from app.core.tenant import get_org_id
from app.main import app, create_app
from app.models.config_change_log import ConfigChangeLog
from app.schemas.config_change_log import (
    ConfigChangeLogCreate,
    ConfigChangeLogListResponse,
    ConfigChangeLogResponse,
    RollbackPreviewResponse,
)

# ═══════════════════════════════════════════════════════════════════
# ConfigCache 单元测试
# ═══════════════════════════════════════════════════════════════════


class TestConfigCache:
    """ConfigCache 内存缓存测试。"""

    def test_set_and_get(self) -> None:
        cache = ConfigCache()
        cache.set("key1", {"data": 1})
        assert cache.get("key1") == {"data": 1}

    def test_get_missing(self) -> None:
        cache = ConfigCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self) -> None:
        cache = ConfigCache(default_ttl=0.01)
        cache.set("shortlived", "value")
        time.sleep(0.02)
        assert cache.get("shortlived") is None

    def test_custom_ttl(self) -> None:
        cache = ConfigCache(default_ttl=300)
        cache.set("custom", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("custom") is None

    def test_invalidate(self) -> None:
        cache = ConfigCache()
        cache.set("key1", "val")
        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache.invalidate("key1") is False

    def test_invalidate_prefix(self) -> None:
        cache = ConfigCache()
        cache.set("kasaya:agents:1", "a")
        cache.set("kasaya:agents:2", "b")
        cache.set("kasaya:guardrails:1", "c")
        count = cache.invalidate_prefix("kasaya:agents:")
        assert count == 2
        assert cache.get("kasaya:agents:1") is None
        assert cache.get("kasaya:guardrails:1") == "c"

    def test_clear(self) -> None:
        cache = ConfigCache()
        cache.set("a", 1)
        cache.set("b", 2)
        count = cache.clear()
        assert count == 2
        assert cache.size == 0

    def test_size(self) -> None:
        cache = ConfigCache()
        assert cache.size == 0
        cache.set("x", 1)
        assert cache.size == 1


class TestCacheKeyHelpers:
    """缓存 key 工具函数测试。"""

    def test_make_cache_key(self) -> None:
        key = make_cache_key("agents", "abc-123")
        assert key == "kasaya:agents:abc-123"

    def test_make_list_cache_key_no_params(self) -> None:
        key = make_list_cache_key("agents")
        assert key == "kasaya:agents:list:all"

    def test_make_list_cache_key_with_params(self) -> None:
        key = make_list_cache_key("agents", {"limit": 20, "offset": 0})
        assert key.startswith("kasaya:agents:list:")
        assert key != "kasaya:agents:list:all"

    def test_make_list_cache_key_deterministic(self) -> None:
        k1 = make_list_cache_key("agents", {"a": 1, "b": 2})
        k2 = make_list_cache_key("agents", {"b": 2, "a": 1})
        assert k1 == k2  # sort_keys=True 保证顺序无关


# ═══════════════════════════════════════════════════════════════════
# Reload API 测试
# ═══════════════════════════════════════════════════════════════════


def _admin_user() -> MagicMock:
    mock = MagicMock()
    mock.id = "00000000-0000-0000-0000-000000000001"
    mock.role = "admin"
    mock.role_id = None
    return mock


class TestReloadAPI:
    """Config reload API 端点测试。"""

    def setup_method(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _admin_user()
        config_cache.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        config_cache.clear()

    def test_reload_all(self) -> None:
        config_cache.set("kasaya:agents:1", "val")
        config_cache.set("kasaya:guardrails:1", "val")

        client = TestClient(app)
        resp = client.post("/api/v1/config/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 2
        assert config_cache.size == 0

    def test_reload_entity_type(self) -> None:
        config_cache.set("kasaya:agents:1", "val")
        config_cache.set("kasaya:agents:2", "val")
        config_cache.set("kasaya:guardrails:1", "val")

        client = TestClient(app)
        resp = client.post("/api/v1/config/reload/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 2
        # guardrails 应该不受影响
        assert config_cache.get("kasaya:guardrails:1") == "val"

    def test_reload_invalid_entity_type(self) -> None:
        client = TestClient(app)
        resp = client.post("/api/v1/config/reload/invalid")
        assert resp.status_code == 400

    def test_reload_requires_auth(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        resp = client.post("/api/v1/config/reload")
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════
# ConfigChangeLog 模型 + Schema + 服务测试
# ═══════════════════════════════════════════════════════════════════


class TestConfigChangeLogModel:
    """ConfigChangeLog ORM 模型测试。"""

    def test_tablename(self) -> None:
        assert ConfigChangeLog.__tablename__ == "config_change_logs"

    def test_create_instance(self) -> None:
        log = ConfigChangeLog(
            config_key="agent.triage.instructions",
            entity_type="agent",
            entity_id="abc-123",
            old_value={"instructions": "old"},
            new_value={"instructions": "new"},
            change_source="api",
        )
        assert log.config_key == "agent.triage.instructions"
        assert log.entity_type == "agent"
        assert log.rollback_ref is None


class TestConfigChangeLogSchema:
    """ConfigChangeLog Schema 测试。"""

    def test_create_schema(self) -> None:
        data = ConfigChangeLogCreate(
            config_key="agent.x.model",
            entity_type="agent",
            entity_id="id-1",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4o"},
        )
        assert data.change_source == "api"
        assert data.description == ""

    def test_response_from_attributes(self) -> None:
        now = datetime.now(UTC)
        mock = MagicMock()
        mock.id = uuid.uuid4()
        mock.config_key = "agent.test"
        mock.entity_type = "agent"
        mock.entity_id = "e-1"
        mock.old_value = None
        mock.new_value = {"a": 1}
        mock.changed_by = None
        mock.change_source = "api"
        mock.rollback_ref = None
        mock.description = ""
        mock.org_id = None
        mock.created_at = now
        resp = ConfigChangeLogResponse.model_validate(mock, from_attributes=True)
        assert resp.config_key == "agent.test"

    def test_list_response(self) -> None:
        resp = ConfigChangeLogListResponse(data=[], total=0)
        assert resp.total == 0

    def test_rollback_preview(self) -> None:
        preview = RollbackPreviewResponse(
            change_id=uuid.uuid4(),
            config_key="agent.x",
            entity_type="agent",
            entity_id="id-1",
            current_value={"v": 2},
            rollback_to_value={"v": 1},
        )
        assert preview.current_value == {"v": 2}


class TestConfigChangeService:
    """配置变更审计服务测试。"""

    @pytest.mark.asyncio
    async def test_record_change(self) -> None:
        from app.services.config_change import record_change

        db = AsyncMock()

        async def _refresh(obj: object) -> None:
            pass

        db.refresh = _refresh

        data = ConfigChangeLogCreate(
            config_key="agent.test.instructions",
            entity_type="agent",
            entity_id="agent-1",
            old_value={"instructions": "old"},
            new_value={"instructions": "new"},
        )
        log = await record_change(db, data, changed_by=uuid.uuid4())
        assert log.config_key == "agent.test.instructions"
        assert log.change_source == "api"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_change(self) -> None:
        from app.services.config_change import rollback_change

        db = AsyncMock()

        async def _refresh(obj: object) -> None:
            pass

        db.refresh = _refresh

        change = ConfigChangeLog(
            config_key="agent.x.model",
            entity_type="agent",
            entity_id="e-1",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4o"},
            change_source="api",
        )
        change.id = uuid.uuid4()

        rollback_log = await rollback_change(db, change)
        assert rollback_log.change_source == "rollback"
        assert rollback_log.rollback_ref == change.id
        assert rollback_log.old_value == {"model": "gpt-4o"}  # 互换
        assert rollback_log.new_value == {"model": "gpt-4"}


# ═══════════════════════════════════════════════════════════════════
# ConfigChangeLog API 测试
# ═══════════════════════════════════════════════════════════════════


def _make_app():
    test_app = create_app()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.role = "admin"
    mock_user.role_id = None
    mock_user.org_id = None
    test_app.dependency_overrides[get_current_user] = lambda: mock_user
    test_app.dependency_overrides[get_org_id] = lambda: None
    return test_app


class TestChangeLogAPI:
    """配置变更日志 API 测试。"""

    @pytest.mark.asyncio
    async def test_list_change_logs_empty(self) -> None:
        test_app = _make_app()
        mock_db = AsyncMock()
        test_app.dependency_overrides[get_db_original] = lambda: mock_db

        from unittest.mock import patch
        with patch("app.services.config_change.list_change_logs", return_value=([], 0)):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/config/change-logs")
                assert resp.status_code == 200
                assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_get_change_log_not_found(self) -> None:
        test_app = _make_app()
        mock_db = AsyncMock()
        test_app.dependency_overrides[get_db_original] = lambda: mock_db

        from unittest.mock import patch
        with patch("app.services.config_change.get_change_log", return_value=None):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/config/change-logs/{uuid.uuid4()}")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_rollback(self) -> None:
        test_app = _make_app()
        mock_db = AsyncMock()
        test_app.dependency_overrides[get_db_original] = lambda: mock_db

        change = MagicMock()
        change.id = uuid.uuid4()
        change.config_key = "agent.x"
        change.entity_type = "agent"
        change.entity_id = "e-1"
        change.old_value = {"v": 1}
        change.new_value = {"v": 2}

        from unittest.mock import patch
        with patch("app.services.config_change.get_change_log", return_value=change):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/config/preview-rollback/{change.id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["rollback_to_value"] == {"v": 1}
                assert data["current_value"] == {"v": 2}

    @pytest.mark.asyncio
    async def test_rollback_not_found(self) -> None:
        test_app = _make_app()
        mock_db = AsyncMock()
        test_app.dependency_overrides[get_db_original] = lambda: mock_db

        from unittest.mock import patch
        with patch("app.services.config_change.get_change_log", return_value=None):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/v1/config/rollback/{uuid.uuid4()}")
                assert resp.status_code == 404
