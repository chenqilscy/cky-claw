"""Backend 测试公共 conftest — 全局依赖覆盖。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.deps import get_current_user
from app.core.tenant import get_org_id
from app.main import app


def _mock_admin_user() -> MagicMock:
    """创建拥有 admin 角色的 mock 用户，用于绕过 require_permission 检查。"""
    user = MagicMock()
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user.username = "test-admin"
    user.role = "admin"
    user.role_id = None
    user.org_id = None
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _override_global_deps():
    """全局覆盖 get_org_id 和 get_current_user 依赖，避免未认证测试触发 401/403。

    需要真实值的测试可自行设置 dependency_overrides 覆盖此默认值。
    """
    app.dependency_overrides[get_org_id] = lambda: None
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_org_id, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _mock_token_cache_redis():
    """全局 mock token_cache 使用的 Redis，确保每次测试都 cache miss。

    避免真实 Redis 缓存干扰 httpx mock 测试。
    """
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    with patch("app.services.token_cache.get_redis", return_value=mock_redis):
        yield
