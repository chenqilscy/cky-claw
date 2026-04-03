"""Model Provider 管理 API 单元测试。

使用 FastAPI TestClient + mock service 层 + mock crypto 模块。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.deps import require_admin as require_admin_original
from app.core.exceptions import NotFoundError
from app.main import app
from app.schemas.provider import ProviderCreate, ProviderResponse, ProviderUpdate
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _fake_admin() -> MagicMock:
    """构造一个假的 Admin 用户用于绕过认证。"""
    user = MagicMock()
    user.role = "admin"
    return user


def _make_provider(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 ProviderConfig ORM 对象。"""
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-openai",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_encrypted": "gAAAAABk...",
        "auth_type": "api_key",
        "auth_config": {},
        "rate_limit_rpm": None,
        "rate_limit_tpm": None,
        "is_enabled": True,
        "org_id": None,
        "last_health_check": None,
        "health_status": "unknown",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _setup_overrides() -> None:
    """设置 DB + Admin 依赖覆盖。"""
    app.dependency_overrides[get_db_original] = lambda: AsyncMock()
    app.dependency_overrides[require_admin_original] = _fake_admin


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestProviderSchemas:
    """Pydantic Schema 校验。"""

    def test_create_valid(self) -> None:
        data = ProviderCreate(
            name="openai", provider_type="openai",
            base_url="https://api.openai.com/v1", api_key="sk-xxx",
        )
        assert data.name == "openai"
        assert data.auth_type == "api_key"

    def test_create_invalid_provider_type(self) -> None:
        with pytest.raises(ValueError, match="provider_type"):
            ProviderCreate(
                name="bad", provider_type="invalid_vendor",
                base_url="https://x.com", api_key="sk-x",
            )

    def test_create_invalid_auth_type(self) -> None:
        with pytest.raises(ValueError, match="auth_type"):
            ProviderCreate(
                name="bad", provider_type="openai",
                base_url="https://x.com", api_key="sk-x",
                auth_type="bearer_only",
            )

    def test_create_name_too_long(self) -> None:
        with pytest.raises(ValueError):
            ProviderCreate(
                name="a" * 65, provider_type="openai",
                base_url="https://x.com", api_key="sk-x",
            )

    def test_create_empty_api_key(self) -> None:
        with pytest.raises(ValueError):
            ProviderCreate(
                name="openai", provider_type="openai",
                base_url="https://x.com", api_key="",
            )

    def test_create_rate_limit_negative(self) -> None:
        with pytest.raises(ValueError):
            ProviderCreate(
                name="openai", provider_type="openai",
                base_url="https://x.com", api_key="sk-x",
                rate_limit_rpm=-1,
            )

    def test_update_partial(self) -> None:
        data = ProviderUpdate(name="new-name")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"name": "new-name"}

    def test_update_empty_is_valid(self) -> None:
        data = ProviderUpdate()
        assert data.model_dump(exclude_unset=True) == {}

    def test_update_invalid_provider_type(self) -> None:
        with pytest.raises(ValueError, match="provider_type"):
            ProviderUpdate(provider_type="invalid_vendor")

    def test_update_invalid_auth_type(self) -> None:
        with pytest.raises(ValueError, match="auth_type"):
            ProviderUpdate(auth_type="bearer_only")

    def test_update_rate_limit_negative(self) -> None:
        with pytest.raises(ValueError):
            ProviderUpdate(rate_limit_rpm=-1)

    def test_response_api_key_not_leaked(self) -> None:
        """ProviderResponse 中只有 api_key_set 布尔值，不包含密钥。"""
        resp = ProviderResponse(
            id=uuid.uuid4(), name="test", provider_type="openai",
            base_url="https://x.com", api_key_set=True,
            auth_type="api_key", auth_config={},
            rate_limit_rpm=None, rate_limit_tpm=None,
            is_enabled=True, org_id=None,
            last_health_check=None, health_status="unknown",
            created_at=_NOW, updated_at=_NOW,
        )
        dumped = resp.model_dump()
        assert "api_key" not in dumped
        assert "api_key_encrypted" not in dumped
        assert dumped["api_key_set"] is True

    def test_all_valid_provider_types(self) -> None:
        for pt in ("openai", "anthropic", "azure", "deepseek", "qwen",
                    "doubao", "zhipu", "moonshot", "custom"):
            data = ProviderCreate(
                name="t", provider_type=pt,
                base_url="https://x.com", api_key="k",
            )
            assert data.provider_type == pt

    def test_all_valid_auth_types(self) -> None:
        for at in ("api_key", "azure_ad", "custom_header"):
            data = ProviderCreate(
                name="t", provider_type="openai",
                base_url="https://x.com", api_key="k",
                auth_type=at,
            )
            assert data.auth_type == at


# ---------------------------------------------------------------------------
# 加密工具测试
# ---------------------------------------------------------------------------


class TestCrypto:
    """encrypt_api_key / decrypt_api_key 测试。"""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        from app.core.crypto import decrypt_api_key, encrypt_api_key
        plain = "sk-test-key-1234567890"
        cipher = encrypt_api_key(plain)
        assert cipher != plain
        assert decrypt_api_key(cipher) == plain

    def test_different_ciphertexts_for_same_plaintext(self) -> None:
        """Fernet 每次加密含随机 IV，相同明文不同密文。"""
        from app.core.crypto import encrypt_api_key
        c1 = encrypt_api_key("same-key")
        c2 = encrypt_api_key("same-key")
        assert c1 != c2

    def test_empty_key_encrypt(self) -> None:
        from app.core.crypto import encrypt_api_key
        cipher = encrypt_api_key("")
        assert cipher  # 不报错，但空字符串也是合法密文


# ---------------------------------------------------------------------------
# API 端点测试（mock service 层）
# ---------------------------------------------------------------------------


class TestProviderAPI:
    """Provider CRUD API 端点测试。"""

    @patch("app.api.providers.provider_service")
    def test_list_providers_empty(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_providers = AsyncMock(return_value=([], 0))
        _setup_overrides()
        try:
            resp = client.get("/api/v1/providers")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    @patch("app.api.providers.provider_service")
    def test_list_providers_with_data(self, mock_svc: MagicMock, client: TestClient) -> None:
        p = _make_provider()
        mock_svc.list_providers = AsyncMock(return_value=([p], 1))
        _setup_overrides()
        try:
            resp = client.get("/api/v1/providers")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["name"] == "test-openai"
        assert body["data"][0]["api_key_set"] is True
        assert "api_key_encrypted" not in body["data"][0]

    @patch("app.api.providers.provider_service")
    def test_list_providers_filter_enabled(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_providers = AsyncMock(return_value=([], 0))
        _setup_overrides()
        try:
            resp = client.get("/api/v1/providers?is_enabled=true&provider_type=openai")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        mock_svc.list_providers.assert_called_once()
        call_kwargs = mock_svc.list_providers.call_args
        assert call_kwargs.kwargs.get("is_enabled") is True
        assert call_kwargs.kwargs.get("provider_type") == "openai"

    @patch("app.api.providers.provider_service")
    def test_create_provider_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        p = _make_provider(name="new-provider")
        mock_svc.create_provider = AsyncMock(return_value=p)
        _setup_overrides()
        try:
            resp = client.post("/api/v1/providers", json={
                "name": "new-provider",
                "provider_type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test-key",
            })
        finally:
            _clear_overrides()

        assert resp.status_code == 201
        assert resp.json()["name"] == "new-provider"

    def test_create_provider_invalid_type(self, client: TestClient) -> None:
        _setup_overrides()
        try:
            resp = client.post("/api/v1/providers", json={
                "name": "bad",
                "provider_type": "invalid_vendor",
                "base_url": "https://x.com",
                "api_key": "sk-x",
            })
        finally:
            _clear_overrides()
        assert resp.status_code == 422

    def test_create_provider_missing_api_key(self, client: TestClient) -> None:
        _setup_overrides()
        try:
            resp = client.post("/api/v1/providers", json={
                "name": "bad",
                "provider_type": "openai",
                "base_url": "https://x.com",
            })
        finally:
            _clear_overrides()
        assert resp.status_code == 422

    @patch("app.api.providers.provider_service")
    def test_get_provider_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        p = _make_provider(id=pid)
        mock_svc.get_provider = AsyncMock(return_value=p)
        _setup_overrides()
        try:
            resp = client.get(f"/api/v1/providers/{pid}")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["name"] == "test-openai"

    @patch("app.api.providers.provider_service")
    def test_get_provider_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.get_provider = AsyncMock(side_effect=NotFoundError(f"Provider '{pid}' 不存在"))
        _setup_overrides()
        try:
            resp = client.get(f"/api/v1/providers/{pid}")
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @patch("app.api.providers.provider_service")
    def test_update_provider_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        p = _make_provider(id=pid, name="updated-name")
        mock_svc.update_provider = AsyncMock(return_value=p)
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}", json={"name": "updated-name"})
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"

    @patch("app.api.providers.provider_service")
    def test_update_provider_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.update_provider = AsyncMock(side_effect=NotFoundError(f"Provider '{pid}' 不存在"))
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}", json={"name": "x"})
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @patch("app.api.providers.provider_service")
    def test_delete_provider_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.delete_provider = AsyncMock(return_value=None)
        _setup_overrides()
        try:
            resp = client.delete(f"/api/v1/providers/{pid}")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["message"] == "Provider deleted"

    @patch("app.api.providers.provider_service")
    def test_delete_provider_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.delete_provider = AsyncMock(side_effect=NotFoundError(f"Provider '{pid}' 不存在"))
        _setup_overrides()
        try:
            resp = client.delete(f"/api/v1/providers/{pid}")
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @patch("app.api.providers.provider_service")
    def test_toggle_provider_enable(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        p = _make_provider(id=pid, is_enabled=True)
        mock_svc.toggle_provider = AsyncMock(return_value=p)
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}/toggle", json={"is_enabled": True})
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is True

    @patch("app.api.providers.provider_service")
    def test_toggle_provider_disable(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        p = _make_provider(id=pid, is_enabled=False)
        mock_svc.toggle_provider = AsyncMock(return_value=p)
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}/toggle", json={"is_enabled": False})
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

    @patch("app.api.providers.provider_service")
    def test_toggle_provider_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.toggle_provider = AsyncMock(side_effect=NotFoundError(f"Provider '{pid}' 不存在"))
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}/toggle", json={"is_enabled": True})
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    def test_toggle_provider_missing_body(self, client: TestClient) -> None:
        pid = uuid.uuid4()
        _setup_overrides()
        try:
            resp = client.put(f"/api/v1/providers/{pid}/toggle")
        finally:
            _clear_overrides()
        assert resp.status_code == 422

    @patch("app.api.providers.provider_service")
    def test_list_providers_pagination(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_providers = AsyncMock(return_value=([], 0))
        _setup_overrides()
        try:
            resp = client.get("/api/v1/providers?limit=5&offset=10")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 5
        assert body["offset"] == 10

    def test_unauthenticated_request_rejected(self, client: TestClient) -> None:
        """无认证凭证时应返回 401/403。"""
        resp = client.get("/api/v1/providers")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 路由注册测试
# ---------------------------------------------------------------------------


class TestProviderRouteRegistration:
    """验证路由已注册到应用。"""

    def test_provider_routes_registered(self) -> None:
        paths = [route.path for route in app.routes]
        assert "/api/v1/providers" in paths
        assert "/api/v1/providers/{provider_id}" in paths
        assert "/api/v1/providers/{provider_id}/toggle" in paths
        assert "/api/v1/providers/{provider_id}/test" in paths


# ---------------------------------------------------------------------------
# Phase 7.7: Multi-Provider 新增测试
# ---------------------------------------------------------------------------


class TestProviderTestResult:
    """ProviderTestResult Schema 测试。"""

    def test_success_result(self) -> None:
        from app.schemas.provider import ProviderTestResult

        r = ProviderTestResult(success=True, latency_ms=230, model_used="gpt-4o-mini")
        assert r.success is True
        assert r.latency_ms == 230
        assert r.error is None

    def test_failure_result(self) -> None:
        from app.schemas.provider import ProviderTestResult

        r = ProviderTestResult(success=False, latency_ms=50, error="Invalid API Key")
        assert r.success is False
        assert r.error == "Invalid API Key"

    def test_defaults(self) -> None:
        from app.schemas.provider import ProviderTestResult

        r = ProviderTestResult(success=True)
        assert r.latency_ms == 0
        assert r.error is None
        assert r.model_used is None


class TestProviderTestAPI:
    """Provider 连通性测试 API 测试。"""

    @patch("app.api.providers.provider_service")
    def test_test_connection_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.test_connection = AsyncMock(return_value={
            "success": True, "latency_ms": 200, "error": None, "model_used": "gpt-4o-mini",
        })
        _setup_overrides()
        try:
            resp = client.post(f"/api/v1/providers/{pid}/test")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["latency_ms"] == 200
        assert body["model_used"] == "gpt-4o-mini"

    @patch("app.api.providers.provider_service")
    def test_test_connection_failure(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.test_connection = AsyncMock(return_value={
            "success": False, "latency_ms": 100, "error": "Invalid API Key", "model_used": "gpt-4o-mini",
        })
        _setup_overrides()
        try:
            resp = client.post(f"/api/v1/providers/{pid}/test")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "Invalid API Key"

    @patch("app.api.providers.provider_service")
    def test_test_connection_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        pid = uuid.uuid4()
        mock_svc.test_connection = AsyncMock(side_effect=NotFoundError(f"Provider '{pid}' 不存在"))
        _setup_overrides()
        try:
            resp = client.post(f"/api/v1/providers/{pid}/test")
        finally:
            _clear_overrides()

        assert resp.status_code == 404


class TestDefaultTestModels:
    """_DEFAULT_TEST_MODELS 映射测试。"""

    def test_known_provider_types(self) -> None:
        from app.services.provider import _DEFAULT_TEST_MODELS

        assert "openai" in _DEFAULT_TEST_MODELS
        assert "anthropic" in _DEFAULT_TEST_MODELS
        assert "deepseek" in _DEFAULT_TEST_MODELS
        assert "qwen" in _DEFAULT_TEST_MODELS
        assert "azure" in _DEFAULT_TEST_MODELS

    def test_all_schema_types_have_default_model(self) -> None:
        from app.schemas.provider import _VALID_PROVIDER_TYPES
        from app.services.provider import _DEFAULT_TEST_MODELS

        for pt in _VALID_PROVIDER_TYPES:
            assert pt in _DEFAULT_TEST_MODELS, f"缺少 provider_type '{pt}' 的默认测试模型"


class TestAgentProviderNameSchema:
    """Agent Schema 中 provider_name 字段测试。"""

    def test_create_with_provider_name(self) -> None:
        a = AgentCreate(name="test-agent", provider_name="my-openai")
        assert a.provider_name == "my-openai"

    def test_create_without_provider_name(self) -> None:
        a = AgentCreate(name="test-agent")
        assert a.provider_name is None

    def test_update_with_provider_name(self) -> None:
        u = AgentUpdate(provider_name="my-deepseek")
        assert u.provider_name == "my-deepseek"

    def test_response_includes_provider_name(self) -> None:
        r = AgentResponse(
            id=uuid.uuid4(),
            name="test-agent",
            description="",
            instructions="",
            model="gpt-4o",
            provider_name="my-openai",
            model_settings=None,
            tool_groups=[],
            handoffs=[],
            guardrails={"input": [], "output": [], "tool": []},
            approval_mode="suggest",
            mcp_servers=[],
            agent_tools=[],
            skills=[],
            output_type=None,
            metadata_={},
            org_id=None,
            is_active=True,
            created_by=None,
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert r.provider_name == "my-openai"


class TestResolveProvider:
    """_resolve_provider 运行时桥接测试。"""

    @pytest.mark.asyncio
    async def test_no_provider_name_returns_empty(self) -> None:
        from app.services.session import _resolve_provider

        mock_config = MagicMock()
        mock_config.provider_name = None
        mock_config.name = "test-agent"
        result = await _resolve_provider(AsyncMock(), mock_config)
        assert result == {}

    @pytest.mark.asyncio
    async def test_provider_not_found_returns_empty(self) -> None:
        from app.services.session import _resolve_provider

        mock_config = MagicMock()
        mock_config.provider_name = "nonexistent"
        mock_config.name = "test-agent"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _resolve_provider(mock_db, mock_config)
        assert result == {}

    @pytest.mark.asyncio
    async def test_provider_disabled_raises(self) -> None:
        from app.services.session import _resolve_provider

        mock_config = MagicMock()
        mock_config.provider_name = "disabled-provider"
        mock_config.name = "test-agent"

        mock_provider = MagicMock()
        mock_provider.is_enabled = False
        mock_provider.name = "disabled-provider"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_provider
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError, match="已被禁用"):
            await _resolve_provider(mock_db, mock_config)

    @pytest.mark.asyncio
    @patch("app.core.crypto.decrypt_api_key", return_value="sk-test-123")
    async def test_provider_found_returns_kwargs(self, _mock_decrypt: MagicMock) -> None:
        from app.services.session import _resolve_provider

        mock_config = MagicMock()
        mock_config.provider_name = "my-openai"
        mock_config.name = "test-agent"

        mock_provider = MagicMock()
        mock_provider.is_enabled = True
        mock_provider.name = "my-openai"
        mock_provider.provider_type = "openai"
        mock_provider.api_key_encrypted = "encrypted_key"
        mock_provider.base_url = "https://custom.openai.com/v1"
        mock_provider.auth_config = {}

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_provider
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _resolve_provider(mock_db, mock_config)
        assert result["api_key"] == "sk-test-123"
        assert result["api_base"] == "https://custom.openai.com/v1"

    @pytest.mark.asyncio
    @patch("app.core.crypto.decrypt_api_key", side_effect=Exception("decrypt failed"))
    async def test_provider_decrypt_failure_raises(self, _mock_decrypt: MagicMock) -> None:
        from app.services.session import _resolve_provider

        mock_config = MagicMock()
        mock_config.provider_name = "broken"
        mock_config.name = "test-agent"

        mock_provider = MagicMock()
        mock_provider.is_enabled = True
        mock_provider.name = "broken"
        mock_provider.provider_type = "openai"
        mock_provider.api_key_encrypted = "bad_cipher"
        mock_provider.base_url = ""
        mock_provider.auth_config = {}

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_provider
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError, match="解密失败"):
            await _resolve_provider(mock_db, mock_config)
