"""Agent 版本管理 API 单元测试。

使用 mock service 层测试 API + Schema + 路由注册。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.main import app
from app.schemas.agent_version import (
    AgentRollbackRequest,
    AgentVersionDiffResponse,
    AgentVersionListResponse,
    AgentVersionResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_AGENT_ID = uuid.uuid4()
_NOW = datetime.now(timezone.utc)


def _make_version(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 AgentConfigVersion ORM 对象。"""
    defaults = {
        "id": uuid.uuid4(),
        "agent_config_id": _AGENT_ID,
        "version": 1,
        "snapshot": {
            "name": "test-agent",
            "description": "desc",
            "instructions": "inst",
            "model": "gpt-4o",
            "model_settings": None,
            "tool_groups": [],
            "handoffs": [],
            "guardrails": {"input": [], "output": [], "tool": []},
            "approval_mode": "suggest",
            "mcp_servers": [],
            "agent_tools": [],
            "skills": [],
            "metadata": {},
        },
        "change_summary": "初始创建",
        "created_by": None,
        "created_at": _NOW,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_agent(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 AgentConfig ORM 对象。"""
    defaults = {
        "id": _AGENT_ID,
        "name": "test-agent",
        "is_active": True,
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
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestAgentVersionSchemas:
    """Pydantic Schema 校验。"""

    def test_version_response_from_orm(self) -> None:
        mock = _make_version()
        resp = AgentVersionResponse.model_validate(mock, from_attributes=True)
        assert resp.version == 1
        assert resp.snapshot["name"] == "test-agent"
        assert resp.change_summary == "初始创建"

    def test_version_list_response(self) -> None:
        resp = AgentVersionListResponse(data=[], total=0)
        assert resp.total == 0
        assert resp.data == []

    def test_diff_response(self) -> None:
        resp = AgentVersionDiffResponse(
            version_a=1,
            version_b=2,
            snapshot_a={"name": "a"},
            snapshot_b={"name": "b"},
        )
        assert resp.version_a == 1
        assert resp.snapshot_b["name"] == "b"

    def test_rollback_request_defaults(self) -> None:
        req = AgentRollbackRequest()
        assert req.change_summary is None

    def test_rollback_request_with_summary(self) -> None:
        req = AgentRollbackRequest(change_summary="回滚原因")
        assert req.change_summary == "回滚原因"


# ---------------------------------------------------------------------------
# API 端点测试（mock service 层）
# ---------------------------------------------------------------------------


class TestAgentVersionAPI:
    """Agent 版本 API 端点测试。"""

    @patch("app.api.agent_versions.version_service")
    def test_list_versions_empty(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.list_versions = AsyncMock(return_value=([], 0))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    @patch("app.api.agent_versions.version_service")
    def test_list_versions_with_data(self, mock_svc: MagicMock, client: TestClient) -> None:
        ver = _make_version()
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.list_versions = AsyncMock(return_value=([ver], 1))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["version"] == 1

    @patch("app.api.agent_versions.version_service")
    def test_list_versions_agent_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_id = AsyncMock(side_effect=NotFoundError("Agent 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.agent_versions.version_service")
    def test_get_version_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        ver = _make_version(version=3)
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.get_version = AsyncMock(return_value=ver)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions/3")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["version"] == 3

    @patch("app.api.agent_versions.version_service")
    def test_get_version_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.get_version = AsyncMock(side_effect=NotFoundError("版本 v99 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions/99")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.agent_versions.version_service")
    def test_rollback_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        new_ver = _make_version(version=4, change_summary="回滚至 v2")
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.rollback_to_version = AsyncMock(return_value=new_ver)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post(f"/api/v1/agents/{_AGENT_ID}/versions/2/rollback")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        assert resp.json()["version"] == 4
        assert resp.json()["change_summary"] == "回滚至 v2"

    @patch("app.api.agent_versions.version_service")
    def test_rollback_with_summary(self, mock_svc: MagicMock, client: TestClient) -> None:
        new_ver = _make_version(version=5, change_summary="自定义原因")
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.rollback_to_version = AsyncMock(return_value=new_ver)

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post(
                f"/api/v1/agents/{_AGENT_ID}/versions/2/rollback",
                json={"change_summary": "自定义原因"},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        assert resp.json()["change_summary"] == "自定义原因"

    @patch("app.api.agent_versions.version_service")
    def test_rollback_version_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.rollback_to_version = AsyncMock(side_effect=NotFoundError("版本 v99 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post(f"/api/v1/agents/{_AGENT_ID}/versions/99/rollback")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.agent_versions.version_service")
    def test_diff_versions_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        ver1 = _make_version(version=1, snapshot={"name": "v1-name"})
        ver2 = _make_version(version=2, snapshot={"name": "v2-name"})
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.get_version = AsyncMock(side_effect=[ver1, ver2])

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions/diff?v1=1&v2=2")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["version_a"] == 1
        assert body["version_b"] == 2
        assert body["snapshot_a"]["name"] == "v1-name"
        assert body["snapshot_b"]["name"] == "v2-name"

    @patch("app.api.agent_versions.version_service")
    def test_diff_version_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.get_agent_by_id = AsyncMock(return_value=_make_agent())
        mock_svc.get_version = AsyncMock(side_effect=NotFoundError("版本 v99 不存在"))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get(f"/api/v1/agents/{_AGENT_ID}/versions/diff?v1=1&v2=99")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Service 层单元测试
# ---------------------------------------------------------------------------


class TestSnapshotFromAgent:
    """_snapshot_from_agent 函数测试。"""

    def test_snapshot_fields(self) -> None:
        from app.services.agent_version import _snapshot_from_agent

        agent = MagicMock()
        agent.name = "test-agent"
        agent.description = "desc"
        agent.instructions = "inst"
        agent.model = "gpt-4o"
        agent.model_settings = {"temperature": 0.7}
        agent.tool_groups = ["group1"]
        agent.handoffs = ["agent-b"]
        agent.guardrails = {"input": ["rule1"], "output": [], "tool": []}
        agent.approval_mode = "suggest"
        agent.mcp_servers = []
        agent.agent_tools = ["sub-agent"]
        agent.skills = ["skill1"]
        agent.metadata_ = {"key": "val"}

        snap = _snapshot_from_agent(agent)

        assert snap["name"] == "test-agent"
        assert snap["model_settings"] == {"temperature": 0.7}
        assert snap["tool_groups"] == ["group1"]
        assert snap["handoffs"] == ["agent-b"]
        assert snap["agent_tools"] == ["sub-agent"]
        assert snap["metadata"] == {"key": "val"}

    def test_snapshot_none_arrays(self) -> None:
        from app.services.agent_version import _snapshot_from_agent

        agent = MagicMock()
        agent.name = "empty-agent"
        agent.description = ""
        agent.instructions = ""
        agent.model = None
        agent.model_settings = None
        agent.tool_groups = None
        agent.handoffs = None
        agent.guardrails = {}
        agent.approval_mode = "full-auto"
        agent.mcp_servers = None
        agent.agent_tools = None
        agent.skills = None
        agent.metadata_ = {}

        snap = _snapshot_from_agent(agent)

        assert snap["tool_groups"] == []
        assert snap["handoffs"] == []
        assert snap["mcp_servers"] == []
        assert snap["agent_tools"] == []
        assert snap["skills"] == []


# ---------------------------------------------------------------------------
# 路由注册验证
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    """验证路由被正确注册到 FastAPI app。"""

    def test_version_routes_registered(self) -> None:
        routes = [r.path for r in app.routes]
        assert "/api/v1/agents/{agent_id}/versions" in routes
        assert "/api/v1/agents/{agent_id}/versions/diff" in routes
        assert "/api/v1/agents/{agent_id}/versions/{version}" in routes
        assert "/api/v1/agents/{agent_id}/versions/{version}/rollback" in routes


# 依赖注入原始引用
from app.core.database import get_db as get_db_original  # noqa: E402
