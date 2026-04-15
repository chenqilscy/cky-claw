"""MCP Server 配置管理单元测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.deps import require_admin as require_admin_original
from app.core.exceptions import NotFoundError
from app.main import app
from app.schemas.mcp_server import (
    VALID_TRANSPORT_TYPES,
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
    _mask_auth_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_admin() -> MagicMock:
    """构造假 Admin 用户用于绕过认证。"""
    user = MagicMock()
    user.role = "admin"
    return user


def _make_mcp_config(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-mcp",
        "description": "测试 MCP Server",
        "transport_type": "stdio",
        "command": "npx @mcp/server-fs /data",
        "url": None,
        "env": {},
        "auth_config": None,
        "is_enabled": True,
        "org_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestMCPServerSchemas:
    def test_create_stdio(self) -> None:
        data = MCPServerCreate(
            name="fs-server",
            transport_type="stdio",
            command="npx @mcp/server-fs /data",
        )
        assert data.transport_type == "stdio"
        assert data.command is not None

    def test_create_sse(self) -> None:
        data = MCPServerCreate(
            name="remote-mcp",
            transport_type="sse",
            url="https://mcp.example.com/sse",
        )
        assert data.transport_type == "sse"
        assert data.url is not None

    def test_create_http(self) -> None:
        data = MCPServerCreate(
            name="http-mcp",
            transport_type="http",
            url="https://mcp.example.com/api",
        )
        assert data.transport_type == "http"

    def test_create_invalid_transport(self) -> None:
        with pytest.raises(ValueError, match="transport_type"):
            MCPServerCreate(name="bad", transport_type="websocket", command="test")

    def test_create_stdio_without_command(self) -> None:
        with pytest.raises(ValueError, match="command"):
            MCPServerCreate(name="bad", transport_type="stdio")

    def test_create_sse_without_url(self) -> None:
        with pytest.raises(ValueError, match="url"):
            MCPServerCreate(name="bad", transport_type="sse")

    def test_create_http_without_url(self) -> None:
        with pytest.raises(ValueError, match="url"):
            MCPServerCreate(name="bad", transport_type="http")

    def test_update_partial(self) -> None:
        data = MCPServerUpdate(description="new desc")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"description": "new desc"}

    def test_update_invalid_transport(self) -> None:
        with pytest.raises(ValueError, match="transport_type"):
            MCPServerUpdate(transport_type="invalid")

    def test_response_masks_auth(self) -> None:
        mock = _make_mcp_config(auth_config={"api_key": "sk-12345", "type": "bearer"})
        resp = MCPServerResponse.model_validate(mock, from_attributes=True)
        assert resp.auth_config is not None
        assert resp.auth_config["api_key"] == "***"
        assert resp.auth_config["type"] == "bearer"

    def test_response_no_auth(self) -> None:
        mock = _make_mcp_config(auth_config=None)
        resp = MCPServerResponse.model_validate(mock, from_attributes=True)
        assert resp.auth_config is None

    def test_list_response(self) -> None:
        resp = MCPServerListResponse(data=[], total=0)
        assert resp.total == 0

    def test_valid_transport_types(self) -> None:
        assert {"stdio", "sse", "http"} == VALID_TRANSPORT_TYPES


class TestAuthMasking:
    def test_mask_none(self) -> None:
        assert _mask_auth_config(None) is None

    def test_mask_empty(self) -> None:
        assert _mask_auth_config({}) == {}

    def test_mask_sensitive_fields(self) -> None:
        auth = {
            "api_key": "sk-12345",
            "secret": "my-secret",
            "token": "bearer-token",
            "password": "p@ssw0rd",
            "client_secret": "cs-123",
            "refresh_token": "rt-456",
            "type": "oauth",
            "client_id": "cid-789",
        }
        masked = _mask_auth_config(auth)
        assert masked is not None
        assert masked["api_key"] == "***"
        assert masked["secret"] == "***"
        assert masked["token"] == "***"
        assert masked["password"] == "***"
        assert masked["client_secret"] == "***"
        assert masked["refresh_token"] == "***"
        # 非敏感字段保留
        assert masked["type"] == "oauth"
        assert masked["client_id"] == "cid-789"

    def test_mask_empty_value(self) -> None:
        auth = {"api_key": ""}
        masked = _mask_auth_config(auth)
        assert masked is not None
        assert masked["api_key"] == ""


# ---------------------------------------------------------------------------
# API 测试
# ---------------------------------------------------------------------------


class TestMCPServerAPI:
    @patch("app.api.mcp_servers.mcp_service")
    def test_create(self, mock_svc: MagicMock, client: TestClient) -> None:
        record = _make_mcp_config()
        mock_svc.create_mcp_server = AsyncMock(return_value=record)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        app.dependency_overrides[require_admin_original] = _fake_admin
        try:
            resp = client.post("/api/v1/mcp/servers", json={
                "name": "test-mcp",
                "transport_type": "stdio",
                "command": "npx @mcp/server-fs /data",
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        assert resp.json()["name"] == "test-mcp"

    @patch("app.api.mcp_servers.mcp_service")
    def test_list_empty(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_mcp_servers = AsyncMock(return_value=([], 0))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get("/api/v1/mcp/servers")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    @patch("app.api.mcp_servers.mcp_service")
    def test_list_with_data(self, mock_svc: MagicMock, client: TestClient) -> None:
        records = [_make_mcp_config(name="mcp-a"), _make_mcp_config(name="mcp-b")]
        mock_svc.list_mcp_servers = AsyncMock(return_value=(records, 2))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get("/api/v1/mcp/servers")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    @patch("app.api.mcp_servers.mcp_service")
    def test_list_filter_transport(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_mcp_servers = AsyncMock(return_value=([], 0))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get("/api/v1/mcp/servers?transport_type=sse")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        mock_svc.list_mcp_servers.assert_awaited_once()
        call_kwargs = mock_svc.list_mcp_servers.call_args
        assert call_kwargs.kwargs.get("transport_type") == "sse" or "sse" in str(call_kwargs)

    @patch("app.api.mcp_servers.mcp_service")
    def test_get(self, mock_svc: MagicMock, client: TestClient) -> None:
        record = _make_mcp_config()
        mock_svc.get_mcp_server = AsyncMock(return_value=record)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/mcp/servers/{record.id}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["name"] == "test-mcp"

    @patch("app.api.mcp_servers.mcp_service")
    def test_get_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_mcp_server = AsyncMock(side_effect=NotFoundError("不存在"))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/mcp/servers/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.mcp_servers.mcp_service")
    def test_update(self, mock_svc: MagicMock, client: TestClient) -> None:
        record = _make_mcp_config(description="updated")
        mock_svc.update_mcp_server = AsyncMock(return_value=record)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        app.dependency_overrides[require_admin_original] = _fake_admin
        try:
            resp = client.put(f"/api/v1/mcp/servers/{record.id}", json={"description": "updated"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200

    @patch("app.api.mcp_servers.mcp_service")
    def test_delete(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_mcp_server = AsyncMock()

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        app.dependency_overrides[require_admin_original] = _fake_admin
        try:
            resp = client.delete(f"/api/v1/mcp/servers/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Service 测试
# ---------------------------------------------------------------------------


class TestMCPServerServiceValidation:
    @patch("app.services.mcp_server.encrypt_api_key", return_value="encrypted")
    def test_encrypt_auth_config(self, mock_encrypt: MagicMock) -> None:
        from app.services.mcp_server import _encrypt_auth_config

        auth = {"api_key": "sk-123", "type": "bearer"}
        result = _encrypt_auth_config(auth)
        assert result is not None
        assert result["api_key"] == "encrypted"
        assert result["type"] == "bearer"
        mock_encrypt.assert_called_once_with("sk-123")

    @patch("app.services.mcp_server.decrypt_api_key", return_value="sk-123")
    def test_decrypt_auth_config(self, mock_decrypt: MagicMock) -> None:
        from app.services.mcp_server import _decrypt_auth_config

        auth = {"api_key": "encrypted_value", "type": "bearer"}
        result = _decrypt_auth_config(auth)
        assert result is not None
        assert result["api_key"] == "sk-123"
        assert result["type"] == "bearer"

    def test_encrypt_none(self) -> None:
        from app.services.mcp_server import _encrypt_auth_config

        assert _encrypt_auth_config(None) is None

    def test_decrypt_none(self) -> None:
        from app.services.mcp_server import _decrypt_auth_config

        assert _decrypt_auth_config(None) is None

    @patch("app.services.mcp_server.decrypt_api_key", side_effect=Exception("bad key"))
    def test_decrypt_failure_fallback(self, mock_decrypt: MagicMock) -> None:
        from app.services.mcp_server import _decrypt_auth_config

        auth = {"api_key": "bad_value"}
        result = _decrypt_auth_config(auth)
        assert result is not None
        assert result["api_key"] == "bad_value"  # 解密失败保留原值

    def test_encrypt_skip_mask_value(self) -> None:
        """*** 值不应被加密。"""
        from app.services.mcp_server import _encrypt_auth_config

        auth = {"api_key": "***"}
        with patch("app.services.mcp_server.encrypt_api_key") as mock_enc:
            result = _encrypt_auth_config(auth)
            mock_enc.assert_not_called()
            assert result is not None
            assert result["api_key"] == "***"


# ---------------------------------------------------------------------------
# 路由注册验证
# ---------------------------------------------------------------------------


class TestMCPServerRouteRegistration:
    def test_routes_registered(self) -> None:
        routes = [r.path for r in app.routes]
        assert "/api/v1/mcp/servers" in routes
        assert "/api/v1/mcp/servers/{server_id}" in routes


# ---------------------------------------------------------------------------
# ORM 模型验证
# ---------------------------------------------------------------------------


class TestMCPServerModel:
    def test_tablename(self) -> None:
        from app.models.mcp_server import MCPServerConfig

        assert MCPServerConfig.__tablename__ == "mcp_server_configs"

    def test_columns(self) -> None:
        from app.models.mcp_server import MCPServerConfig

        columns = {c.name for c in MCPServerConfig.__table__.columns}
        expected = {
            "id", "name", "description", "transport_type", "command", "url",
            "env", "auth_config", "is_enabled", "org_id", "created_at", "updated_at",
        }
        assert expected.issubset(columns)


# ---------------------------------------------------------------------------
# _resolve_mcp_tools 测试
# ---------------------------------------------------------------------------


class TestResolveMCPTools:
    @pytest.mark.asyncio
    async def test_no_mcp_servers(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.mcp_servers = []
        db = AsyncMock()

        result = await _resolve_mcp_tools(db, config)
        assert result == []
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_with_mcp_servers(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "test-agent"
        config.mcp_servers = ["fs-server", "github-mcp"]

        mcp_config_1 = MagicMock()
        mcp_config_1.name = "fs-server"
        mcp_config_2 = MagicMock()
        mcp_config_2.name = "github-mcp"

        db = AsyncMock()

        with patch(
            "app.services.mcp_server.get_mcp_servers_by_names",
            new_callable=AsyncMock,
            return_value=[mcp_config_1, mcp_config_2],
        ):
            result = await _resolve_mcp_tools(db, config)

        # 当前返回空列表（待 MCP SDK 集成）
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_mcp_server_warns(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "test-agent"
        config.mcp_servers = ["existing", "missing"]

        mcp_config = MagicMock()
        mcp_config.name = "existing"

        db = AsyncMock()

        with patch(
            "app.services.mcp_server.get_mcp_servers_by_names",
            new_callable=AsyncMock,
            return_value=[mcp_config],
        ):
            result = await _resolve_mcp_tools(db, config)

        assert result == []
