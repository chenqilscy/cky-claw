"""Agent CRUD API 单元测试。

使用 httpx.AsyncClient + SQLite 内存数据库，不依赖 PostgreSQL。
由于 SQLite 不支持 ARRAY 和 JSONB，我们使用 mock 方式测试 service 层和 API 层。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, NotFoundError
from app.main import app
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate, GuardrailsConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent_config(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 AgentConfig ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-agent",
        "description": "A test agent",
        "instructions": "You are a test agent.",
        "model": "gpt-4o",
        "provider_name": None,
        "model_settings": None,
        "tool_groups": [],
        "handoffs": [],
        "guardrails": {"input": [], "output": [], "tool": []},
        "approval_mode": "suggest",
        "mcp_servers": [],
        "agent_tools": [],
        "skills": [],
        "metadata_": {},
        "org_id": None,
        "is_active": True,
        "created_by": None,
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
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestAgentSchemas:
    """Pydantic Schema 校验。"""

    def test_create_valid_name(self) -> None:
        data = AgentCreate(name="my-agent", instructions="hello")
        assert data.name == "my-agent"

    def test_create_invalid_name_uppercase(self) -> None:
        with pytest.raises(ValueError, match="名称只能包含"):
            AgentCreate(name="MyAgent", instructions="hello")

    def test_create_invalid_name_too_short(self) -> None:
        with pytest.raises(ValueError):
            AgentCreate(name="ab", instructions="hello")

    def test_create_invalid_name_special_chars(self) -> None:
        with pytest.raises(ValueError, match="名称只能包含"):
            AgentCreate(name="my_agent!", instructions="hello")

    def test_create_invalid_name_starts_with_hyphen(self) -> None:
        with pytest.raises(ValueError, match="名称只能包含"):
            AgentCreate(name="-my-agent", instructions="hello")

    def test_create_valid_approval_modes(self) -> None:
        for mode in ("suggest", "auto-edit", "full-auto"):
            data = AgentCreate(name="test-agent", approval_mode=mode)
            assert data.approval_mode == mode

    def test_create_invalid_approval_mode(self) -> None:
        with pytest.raises(ValueError, match="approval_mode"):
            AgentCreate(name="test-agent", approval_mode="invalid")

    def test_update_partial(self) -> None:
        data = AgentUpdate(description="new desc")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"description": "new desc"}

    def test_update_empty_is_valid(self) -> None:
        data = AgentUpdate()
        assert data.model_dump(exclude_unset=True) == {}

    def test_response_from_orm(self) -> None:
        mock = _make_agent_config()
        resp = AgentResponse.model_validate(mock, from_attributes=True)
        assert resp.name == "test-agent"
        assert resp.metadata == {}

    def test_guardrails_config_defaults(self) -> None:
        g = GuardrailsConfig()
        assert g.input == []
        assert g.output == []
        assert g.tool == []


# ---------------------------------------------------------------------------
# API 端点测试（mock service 层）
# ---------------------------------------------------------------------------


class TestAgentAPI:
    """Agent CRUD API 端点测试。"""

    @patch("app.api.agents.agent_service")
    @patch("app.api.agents.get_db")
    def test_list_agents_empty(self, mock_db: MagicMock, mock_svc: MagicMock, client: TestClient) -> None:
        mock_session = AsyncMock()
        mock_db.return_value = mock_session
        mock_svc.list_agents = AsyncMock(return_value=([], 0))

        # Override dependency
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    @patch("app.api.agents.agent_service")
    def test_list_agents_with_data(self, mock_svc: MagicMock, client: TestClient) -> None:
        agent_mock = _make_agent_config()
        mock_svc.list_agents = AsyncMock(return_value=([agent_mock], 1))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["name"] == "test-agent"

    @patch("app.api.agents.agent_service")
    def test_create_agent_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        agent_mock = _make_agent_config(name="new-agent")
        mock_svc.create_agent = AsyncMock(return_value=agent_mock)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents", json={
                "name": "new-agent",
                "instructions": "You are new.",
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        assert resp.json()["name"] == "new-agent"

    @patch("app.api.agents.agent_service")
    def test_create_agent_conflict(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.create_agent = AsyncMock(side_effect=ConflictError("Agent 名称 'dup' 已存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents", json={
                "name": "dup-agent",
                "instructions": "dup",
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409

    def test_create_agent_invalid_name(self, client: TestClient) -> None:
        resp = client.post("/api/v1/agents", json={
            "name": "INVALID",
            "instructions": "bad",
        })
        assert resp.status_code == 422

    @patch("app.api.agents.agent_service")
    def test_get_agent_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        agent_mock = _make_agent_config()
        mock_svc.get_agent_by_name = AsyncMock(return_value=agent_mock)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents/test-agent")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["name"] == "test-agent"

    @patch("app.api.agents.agent_service")
    def test_get_agent_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_name = AsyncMock(side_effect=NotFoundError("Agent 'nope' 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents/nope")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.agents.agent_service")
    def test_update_agent_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        agent_mock = _make_agent_config(description="updated")
        mock_svc.update_agent = AsyncMock(return_value=agent_mock)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.put("/api/v1/agents/test-agent", json={
                "description": "updated",
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"

    @patch("app.api.agents.agent_service")
    def test_delete_agent_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_agent = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.delete("/api/v1/agents/test-agent")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["message"] == "Agent deleted"

    @patch("app.api.agents.agent_service")
    def test_delete_agent_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_agent = AsyncMock(side_effect=NotFoundError("Agent 'nope' 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.delete("/api/v1/agents/nope")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.agents.agent_service")
    def test_list_agents_with_search(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_agents = AsyncMock(return_value=([], 0))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents?search=data&limit=10&offset=5")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 10
        assert body["offset"] == 5


# ---------------------------------------------------------------------------
# 路由注册测试
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    """验证路由已注册到应用。"""

    def test_agents_routes_registered(self) -> None:
        paths = [route.path for route in app.routes]
        assert "/api/v1/agents" in paths
        assert "/api/v1/agents/{name}" in paths


# 依赖注入原始引用
from app.core.database import get_db as get_db_original  # noqa: E402
