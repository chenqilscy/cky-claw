"""监督面板 API 单元测试。

覆盖：Schema 验证、活跃会话列表、会话详情、暂停/恢复操作、认证保护、路由注册。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.deps import require_admin as require_admin_original
from app.core.exceptions import ConflictError, NotFoundError
from app.main import app
from app.schemas.supervision import (
    MessageItem,
    PauseRequest,
    ResumeRequest,
    SessionStatus,
    SupervisionActionResponse,
    SupervisionSessionDetail,
    SupervisionSessionItem,
    SupervisionSessionListResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
_SESSION_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


def _fake_admin() -> MagicMock:
    user = MagicMock()
    user.role = "admin"
    return user


def _setup_overrides() -> TestClient:
    """配置 TestClient：覆盖 DB 和认证依赖。"""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_original] = lambda: mock_db
    app.dependency_overrides[require_admin_original] = _fake_admin
    client = TestClient(app, raise_server_exceptions=False)
    return client


def _cleanup_overrides() -> None:
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestSupervisionSchemas:
    """监督面板 Schema 校验。"""

    def test_session_status_enum(self) -> None:
        assert SessionStatus.active.value == "active"
        assert SessionStatus.paused.value == "paused"
        assert SessionStatus.completed.value == "completed"

    def test_supervision_session_item(self) -> None:
        item = SupervisionSessionItem(
            session_id=_SESSION_ID,
            agent_name="test-agent",
            status="active",
            title="Test",
            token_used=100,
            call_count=5,
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert item.session_id == _SESSION_ID
        assert item.token_used == 100
        assert item.call_count == 5

    def test_supervision_session_item_defaults(self) -> None:
        item = SupervisionSessionItem(
            session_id=_SESSION_ID,
            agent_name="test-agent",
            status="active",
            title="",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert item.token_used == 0
        assert item.call_count == 0

    def test_supervision_session_detail(self) -> None:
        detail = SupervisionSessionDetail(
            session_id=_SESSION_ID,
            agent_name="test-agent",
            status="active",
            title="Test Session",
            token_used=200,
            call_count=10,
            created_at=_NOW,
            updated_at=_NOW,
            messages=[MessageItem(role="user", content="hello")],
            metadata={"key": "value"},
        )
        assert len(detail.messages) == 1
        assert detail.metadata == {"key": "value"}

    def test_supervision_list_response(self) -> None:
        resp = SupervisionSessionListResponse(data=[], total=0)
        assert resp.data == []
        assert resp.total == 0

    def test_pause_request(self) -> None:
        req = PauseRequest(reason="检查工具调用")
        assert req.reason == "检查工具调用"

    def test_pause_request_default(self) -> None:
        req = PauseRequest()
        assert req.reason == ""

    def test_resume_request(self) -> None:
        req = ResumeRequest(injected_instructions="使用本地数据")
        assert req.injected_instructions == "使用本地数据"

    def test_action_response(self) -> None:
        resp = SupervisionActionResponse(
            session_id=_SESSION_ID,
            status="paused",
            message="会话已暂停",
        )
        assert resp.status == "paused"

    def test_message_item(self) -> None:
        msg = MessageItem(role="user", content="hello", timestamp=_NOW)
        assert msg.role == "user"
        assert msg.timestamp == _NOW

    def test_message_item_no_timestamp(self) -> None:
        msg = MessageItem(role="assistant", content="hi")
        assert msg.timestamp is None


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

_MODULE = "app.services.supervision"


class TestSupervisionAPI:
    """监督面板 API 测试。"""

    def setup_method(self) -> None:
        self.client = _setup_overrides()

    def teardown_method(self) -> None:
        _cleanup_overrides()

    @patch(f"{_MODULE}.list_active_sessions", new_callable=AsyncMock)
    def test_list_active_sessions_empty(self, mock_list: AsyncMock) -> None:
        mock_list.return_value = SupervisionSessionListResponse(data=[], total=0)
        resp = self.client.get("/api/v1/supervision/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["total"] == 0

    @patch(f"{_MODULE}.list_active_sessions", new_callable=AsyncMock)
    def test_list_active_sessions_with_data(self, mock_list: AsyncMock) -> None:
        item = SupervisionSessionItem(
            session_id=_SESSION_ID,
            agent_name="triage-agent",
            status="active",
            title="Test",
            token_used=1200,
            call_count=5,
            created_at=_NOW,
            updated_at=_NOW,
        )
        mock_list.return_value = SupervisionSessionListResponse(data=[item], total=1)
        resp = self.client.get("/api/v1/supervision/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["agent_name"] == "triage-agent"
        assert body["data"][0]["token_used"] == 1200

    @patch(f"{_MODULE}.list_active_sessions", new_callable=AsyncMock)
    def test_list_with_agent_filter(self, mock_list: AsyncMock) -> None:
        mock_list.return_value = SupervisionSessionListResponse(data=[], total=0)
        resp = self.client.get("/api/v1/supervision/sessions?agent_name=test")
        assert resp.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("agent_name") == "test" or call_kwargs[1].get("agent_name") == "test"

    @patch(f"{_MODULE}.list_active_sessions", new_callable=AsyncMock)
    def test_list_with_status_filter(self, mock_list: AsyncMock) -> None:
        mock_list.return_value = SupervisionSessionListResponse(data=[], total=0)
        resp = self.client.get("/api/v1/supervision/sessions?status=paused")
        assert resp.status_code == 200

    @patch(f"{_MODULE}.get_session_detail", new_callable=AsyncMock)
    def test_get_session_detail(self, mock_get: AsyncMock) -> None:
        detail = SupervisionSessionDetail(
            session_id=_SESSION_ID,
            agent_name="test-agent",
            status="active",
            title="Session Detail",
            token_used=500,
            call_count=3,
            created_at=_NOW,
            updated_at=_NOW,
            messages=[],
            metadata={"env": "test"},
        )
        mock_get.return_value = detail
        resp = self.client.get(f"/api/v1/supervision/sessions/{_SESSION_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_name"] == "test-agent"
        assert body["token_used"] == 500
        assert body["metadata"] == {"env": "test"}

    @patch(f"{_MODULE}.get_session_detail", new_callable=AsyncMock)
    def test_get_session_not_found(self, mock_get: AsyncMock) -> None:
        mock_get.side_effect = NotFoundError("Session 不存在")
        resp = self.client.get(f"/api/v1/supervision/sessions/{_SESSION_ID}")
        assert resp.status_code == 404

    @patch(f"{_MODULE}.pause_session", new_callable=AsyncMock)
    def test_pause_session(self, mock_pause: AsyncMock) -> None:
        mock_pause.return_value = SupervisionActionResponse(
            session_id=_SESSION_ID, status="paused", message="会话已暂停"
        )
        resp = self.client.post(
            f"/api/v1/supervision/sessions/{_SESSION_ID}/pause",
            json={"reason": "检查工具调用"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "paused"

    @patch(f"{_MODULE}.pause_session", new_callable=AsyncMock)
    def test_pause_session_no_body(self, mock_pause: AsyncMock) -> None:
        mock_pause.return_value = SupervisionActionResponse(
            session_id=_SESSION_ID, status="paused", message="会话已暂停"
        )
        resp = self.client.post(f"/api/v1/supervision/sessions/{_SESSION_ID}/pause")
        assert resp.status_code == 200

    @patch(f"{_MODULE}.pause_session", new_callable=AsyncMock)
    def test_pause_session_conflict(self, mock_pause: AsyncMock) -> None:
        mock_pause.side_effect = ConflictError("会话当前状态为 'paused'，无法执行此操作")
        resp = self.client.post(
            f"/api/v1/supervision/sessions/{_SESSION_ID}/pause",
            json={"reason": "test"},
        )
        assert resp.status_code == 409

    @patch(f"{_MODULE}.resume_session", new_callable=AsyncMock)
    def test_resume_session(self, mock_resume: AsyncMock) -> None:
        mock_resume.return_value = SupervisionActionResponse(
            session_id=_SESSION_ID, status="active", message="会话已恢复"
        )
        resp = self.client.post(
            f"/api/v1/supervision/sessions/{_SESSION_ID}/resume",
            json={"injected_instructions": "使用本地数据"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"

    @patch(f"{_MODULE}.resume_session", new_callable=AsyncMock)
    def test_resume_session_no_body(self, mock_resume: AsyncMock) -> None:
        mock_resume.return_value = SupervisionActionResponse(
            session_id=_SESSION_ID, status="active", message="会话已恢复"
        )
        resp = self.client.post(f"/api/v1/supervision/sessions/{_SESSION_ID}/resume")
        assert resp.status_code == 200

    @patch(f"{_MODULE}.resume_session", new_callable=AsyncMock)
    def test_resume_session_conflict(self, mock_resume: AsyncMock) -> None:
        mock_resume.side_effect = ConflictError("会话当前状态为 'active'，无法执行此操作")
        resp = self.client.post(
            f"/api/v1/supervision/sessions/{_SESSION_ID}/resume",
            json={},
        )
        assert resp.status_code == 409


class TestSupervisionAuth:
    """监督面板认证测试。"""

    def test_unauthenticated_request_rejected(self) -> None:
        """无认证时应返回 401（HTTPBearer 未提供 token）。"""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/supervision/sessions")
        assert resp.status_code == 401


class TestSupervisionRoutes:
    """监督面板路由注册测试。"""

    def test_supervision_routes_registered(self) -> None:
        routes = [r.path for r in app.routes]
        assert "/api/v1/supervision/sessions" in routes
        assert "/api/v1/supervision/sessions/{session_id}" in routes
        assert "/api/v1/supervision/sessions/{session_id}/pause" in routes
        assert "/api/v1/supervision/sessions/{session_id}/resume" in routes
