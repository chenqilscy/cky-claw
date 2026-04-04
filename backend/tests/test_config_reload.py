"""Config cache + reload API 测试。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.cache import ConfigCache, config_cache, make_cache_key, make_list_cache_key
from app.core.deps import get_current_user
from app.main import app


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
        cache.set("ckyclaw:agents:1", "a")
        cache.set("ckyclaw:agents:2", "b")
        cache.set("ckyclaw:guardrails:1", "c")
        count = cache.invalidate_prefix("ckyclaw:agents:")
        assert count == 2
        assert cache.get("ckyclaw:agents:1") is None
        assert cache.get("ckyclaw:guardrails:1") == "c"

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
        assert key == "ckyclaw:agents:abc-123"

    def test_make_list_cache_key_no_params(self) -> None:
        key = make_list_cache_key("agents")
        assert key == "ckyclaw:agents:list:all"

    def test_make_list_cache_key_with_params(self) -> None:
        key = make_list_cache_key("agents", {"limit": 20, "offset": 0})
        assert key.startswith("ckyclaw:agents:list:")
        assert key != "ckyclaw:agents:list:all"

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
        config_cache.set("ckyclaw:agents:1", "val")
        config_cache.set("ckyclaw:guardrails:1", "val")

        client = TestClient(app)
        resp = client.post("/api/v1/config/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 2
        assert config_cache.size == 0

    def test_reload_entity_type(self) -> None:
        config_cache.set("ckyclaw:agents:1", "val")
        config_cache.set("ckyclaw:agents:2", "val")
        config_cache.set("ckyclaw:guardrails:1", "val")

        client = TestClient(app)
        resp = client.post("/api/v1/config/reload/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 2
        # guardrails 应该不受影响
        assert config_cache.get("ckyclaw:guardrails:1") == "val"

    def test_reload_invalid_entity_type(self) -> None:
        client = TestClient(app)
        resp = client.post("/api/v1/config/reload/invalid")
        assert resp.status_code == 400

    def test_reload_requires_auth(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        resp = client.post("/api/v1/config/reload")
        assert resp.status_code in (401, 403)
