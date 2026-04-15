"""Agent 调试器 API 测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


def _make_debug_session_mock(**overrides) -> MagicMock:
    """构造模拟 DebugSession 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "agent_name": "test-agent",
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "state": "idle",
        "mode": "step_turn",
        "input_message": "你好",
        "current_turn": 0,
        "current_agent_name": "test-agent",
        "pause_context": {},
        "token_usage": {},
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_controller_mock(state: str = "paused") -> MagicMock:
    """构造模拟 DebugController 对象。"""
    ctrl = MagicMock()
    state_mock = MagicMock()
    state_mock.value = state
    ctrl.state = state_mock
    ctrl.step = AsyncMock()
    ctrl.resume = AsyncMock()
    ctrl.stop = AsyncMock()
    ctrl.pause_context = None
    ctrl._on_event = None
    return ctrl


def _make_pause_context_mock(**overrides) -> MagicMock:
    """构造模拟 PauseContext 对象。"""
    defaults = {
        "turn": 1,
        "agent_name": "test-agent",
        "reason": "turn_end",
        "recent_messages": [{"role": "user", "content": "你好"}],
        "last_llm_response": {"content": "你好！"},
        "last_tool_calls": [],
        "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "paused_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# List Sessions — GET /api/v1/debug/sessions
# ---------------------------------------------------------------------------

class TestListDebugSessions:
    """调试会话列表 API 测试。"""

    @patch("app.services.debug.list_debug_sessions", new_callable=AsyncMock)
    def test_list_empty(self, mock_list: AsyncMock, client: TestClient) -> None:
        """无调试会话时返回空列表。"""
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/debug/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    @patch("app.services.debug.list_debug_sessions", new_callable=AsyncMock)
    def test_list_with_data(self, mock_list: AsyncMock, client: TestClient) -> None:
        """有数据时正确返回。"""
        session = _make_debug_session_mock()
        mock_list.return_value = ([session], 1)

        resp = client.get("/api/v1/debug/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["agent_name"] == "test-agent"
        assert body["items"][0]["state"] == "idle"

    @patch("app.services.debug.list_debug_sessions", new_callable=AsyncMock)
    def test_list_with_state_filter(self, mock_list: AsyncMock, client: TestClient) -> None:
        """状态筛选参数正确传递。"""
        mock_list.return_value = ([], 0)

        client.get("/api/v1/debug/sessions?state=paused")
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("state") == "paused"

    @patch("app.services.debug.list_debug_sessions", new_callable=AsyncMock)
    def test_list_pagination(self, mock_list: AsyncMock, client: TestClient) -> None:
        """分页参数正确传递。"""
        mock_list.return_value = ([], 0)

        client.get("/api/v1/debug/sessions?limit=10&offset=5")
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("limit") == 10
        assert call_kwargs.kwargs.get("offset") == 5

    @patch("app.services.debug.list_debug_sessions", new_callable=AsyncMock)
    def test_list_passes_user_id(self, mock_list: AsyncMock, client: TestClient) -> None:
        """列表接口传递当前用户 ID。"""
        mock_list.return_value = ([], 0)

        client.get("/api/v1/debug/sessions")
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("user_id") == uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Create Session — POST /api/v1/debug/sessions
# ---------------------------------------------------------------------------

class TestCreateDebugSession:
    """创建调试会话 API 测试。"""

    @patch("app.services.debug.create_debug_session", new_callable=AsyncMock)
    def test_create_success(self, mock_create: AsyncMock, client: TestClient) -> None:
        """正常创建调试会话。"""
        session = _make_debug_session_mock()
        mock_create.return_value = session

        resp = client.post("/api/v1/debug/sessions", json={
            "agent_id": str(uuid.uuid4()),
            "input_message": "你好",
            "mode": "step_turn",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["agent_name"] == "test-agent"
        assert body["state"] == "idle"
        assert body["mode"] == "step_turn"

    @patch("app.services.debug.create_debug_session", new_callable=AsyncMock)
    def test_create_default_mode(self, mock_create: AsyncMock, client: TestClient) -> None:
        """不指定 mode 时使用默认值。"""
        session = _make_debug_session_mock()
        mock_create.return_value = session

        resp = client.post("/api/v1/debug/sessions", json={
            "agent_id": str(uuid.uuid4()),
            "input_message": "测试",
        })
        assert resp.status_code == 201
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("mode") == "step_turn"

    @patch("app.services.debug.create_debug_session", new_callable=AsyncMock)
    def test_create_agent_not_found(self, mock_create: AsyncMock, client: TestClient) -> None:
        """Agent 不存在时返回 400。"""
        mock_create.side_effect = ValueError("Agent xxx 不存在")

        resp = client.post("/api/v1/debug/sessions", json={
            "agent_id": str(uuid.uuid4()),
            "input_message": "你好",
        })
        assert resp.status_code == 400
        assert "不存在" in resp.json()["detail"]

    @patch("app.services.debug.create_debug_session", new_callable=AsyncMock)
    def test_create_exceeds_limit(self, mock_create: AsyncMock, client: TestClient) -> None:
        """超过最大活跃会话数时返回 400。"""
        mock_create.side_effect = ValueError("活跃调试会话已达上限（5）")

        resp = client.post("/api/v1/debug/sessions", json={
            "agent_id": str(uuid.uuid4()),
            "input_message": "你好",
        })
        assert resp.status_code == 400
        assert "上限" in resp.json()["detail"]

    def test_create_empty_message(self, client: TestClient) -> None:
        """空消息验证失败。"""
        resp = client.post("/api/v1/debug/sessions", json={
            "agent_id": str(uuid.uuid4()),
            "input_message": "",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_create_missing_agent_id(self, client: TestClient) -> None:
        """缺少 agent_id 验证失败。"""
        resp = client.post("/api/v1/debug/sessions", json={
            "input_message": "你好",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get Session — GET /api/v1/debug/sessions/{id}
# ---------------------------------------------------------------------------

class TestGetDebugSession:
    """获取调试会话详情 API 测试。"""

    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_get_success(self, mock_get: AsyncMock, client: TestClient) -> None:
        """正常获取调试会话。"""
        session = _make_debug_session_mock()
        mock_get.return_value = session

        resp = client.get(f"/api/v1/debug/sessions/{session.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_name"] == "test-agent"

    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_get_not_found(self, mock_get: AsyncMock, client: TestClient) -> None:
        """会话不存在时返回 404。"""
        mock_get.return_value = None

        resp = client.get(f"/api/v1/debug/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Step — POST /api/v1/debug/sessions/{id}/step
# ---------------------------------------------------------------------------

class TestStepDebugSession:
    """单步执行 API 测试。"""

    @patch("app.services.debug.update_session_state", new_callable=AsyncMock)
    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_step_success(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, mock_update: AsyncMock, client: TestClient) -> None:
        """正常单步执行。"""
        ctrl = _make_controller_mock()
        session = _make_debug_session_mock(state="paused")
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = ctrl
        mock_update.return_value = session

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/step")
        assert resp.status_code == 200
        ctrl.step.assert_called_once()

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_step_no_controller(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """无活跃控制器时返回 404。"""
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = None

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/step")
        assert resp.status_code == 404
        assert "未激活" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Continue — POST /api/v1/debug/sessions/{id}/continue
# ---------------------------------------------------------------------------

class TestContinueDebugSession:
    """继续执行 API 测试。"""

    @patch("app.services.debug.update_session_state", new_callable=AsyncMock)
    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_continue_success(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, mock_update: AsyncMock, client: TestClient) -> None:
        """正常继续执行。"""
        ctrl = _make_controller_mock()
        session = _make_debug_session_mock(state="running")
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = ctrl
        mock_update.return_value = session

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/continue")
        assert resp.status_code == 200
        ctrl.resume.assert_called_once()

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_continue_no_controller(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """无活跃控制器时返回 404。"""
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = None

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/continue")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Stop — POST /api/v1/debug/sessions/{id}/stop
# ---------------------------------------------------------------------------

class TestStopDebugSession:
    """终止调试会话 API 测试。"""

    @patch("app.services.debug.update_session_state", new_callable=AsyncMock)
    @patch("app.services.debug.cleanup_session", new_callable=AsyncMock)
    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_stop_success(
        self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, mock_cleanup: AsyncMock, mock_update: AsyncMock, client: TestClient,
    ) -> None:
        """正常终止会话。"""
        ctrl = _make_controller_mock()
        session = _make_debug_session_mock(state="failed", error="用户终止")
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = ctrl
        mock_update.return_value = session

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/stop")
        assert resp.status_code == 200
        ctrl.stop.assert_called_once()
        mock_cleanup.assert_called_once_with(session.id)
        body = resp.json()
        assert body["state"] == "failed"
        assert body["error"] == "用户终止"

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_stop_no_controller(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """无活跃控制器时返回 404。"""
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = None

        resp = client.post(f"/api/v1/debug/sessions/{session.id}/stop")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Context — GET /api/v1/debug/sessions/{id}/context
# ---------------------------------------------------------------------------

class TestGetDebugContext:
    """调试上下文 API 测试。"""

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_context_success(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """暂停时正确返回上下文。"""
        ctrl = _make_controller_mock()
        ctrl.pause_context = _make_pause_context_mock()
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = ctrl

        resp = client.get(f"/api/v1/debug/sessions/{session.id}/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["turn"] == 1
        assert body["agent_name"] == "test-agent"
        assert body["reason"] == "turn_end"
        assert len(body["recent_messages"]) == 1
        assert body["last_llm_response"] == {"content": "你好！"}
        assert body["token_usage"]["prompt_tokens"] == 100

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_context_not_paused(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """非暂停状态时返回 400。"""
        ctrl = _make_controller_mock(state="running")
        ctrl.pause_context = None
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = ctrl

        resp = client.get(f"/api/v1/debug/sessions/{session.id}/context")
        assert resp.status_code == 400
        assert "暂停" in resp.json()["detail"]

    @patch("app.services.debug.get_controller")
    @patch("app.services.debug.get_debug_session", new_callable=AsyncMock)
    def test_context_no_controller(self, mock_get_sess: AsyncMock, mock_get_ctrl: MagicMock, client: TestClient) -> None:
        """无活跃控制器时返回 404。"""
        session = _make_debug_session_mock()
        mock_get_sess.return_value = session
        mock_get_ctrl.return_value = None

        resp = client.get(f"/api/v1/debug/sessions/{session.id}/context")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schema 验证测试
# ---------------------------------------------------------------------------

class TestDebugSchemas:
    """Pydantic Schema 验证测试。"""

    def test_session_create_valid(self) -> None:
        """合法请求通过验证。"""
        from app.schemas.debug import DebugSessionCreate
        obj = DebugSessionCreate(
            agent_id=uuid.uuid4(),
            input_message="你好",
            mode="step_turn",
        )
        assert obj.mode == "step_turn"

    def test_session_create_message_too_long(self) -> None:
        """消息超长时验证失败。"""
        from app.schemas.debug import DebugSessionCreate
        with pytest.raises(Exception):
            DebugSessionCreate(
                agent_id=uuid.uuid4(),
                input_message="x" * 4097,
                mode="step_turn",
            )

    def test_session_create_empty_message(self) -> None:
        """空消息验证失败。"""
        from app.schemas.debug import DebugSessionCreate
        with pytest.raises(Exception):
            DebugSessionCreate(
                agent_id=uuid.uuid4(),
                input_message="",
            )

    def test_session_response_from_attributes(self) -> None:
        """DebugSessionResponse 支持 from_attributes 模式。"""
        from app.schemas.debug import DebugSessionResponse
        mock = _make_debug_session_mock()
        resp = DebugSessionResponse.model_validate(mock)
        assert resp.agent_name == "test-agent"
        assert resp.state == "idle"

    def test_context_response_defaults(self) -> None:
        """DebugContextResponse 默认字段。"""
        from app.schemas.debug import DebugContextResponse
        ctx = DebugContextResponse(turn=0, agent_name="a", reason="turn_end")
        assert ctx.recent_messages == []
        assert ctx.last_llm_response is None
        assert ctx.token_usage == {}


# ---------------------------------------------------------------------------
# Service 层测试
# ---------------------------------------------------------------------------

class TestDebugService:
    """调试会话 Service 层测试。"""

    def test_get_controller_not_found(self) -> None:
        """不存在的 session 返回 None。"""
        from app.services.debug import get_controller
        assert get_controller(uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_cleanup_session(self) -> None:
        """cleanup 后 controller 被移除。"""
        from app.services.debug import _active_controllers, cleanup_session

        sid = uuid.uuid4()
        _active_controllers[sid] = MagicMock()
        assert sid in _active_controllers

        await cleanup_session(sid)
        assert sid not in _active_controllers

    @pytest.mark.asyncio
    async def test_cleanup_session_idempotent(self) -> None:
        """对不存在的 session 调用 cleanup 不报错。"""
        from app.services.debug import cleanup_session
        await cleanup_session(uuid.uuid4())  # 不抛异常

    def test_max_active_sessions_constant(self) -> None:
        """MAX_ACTIVE_SESSIONS 值为 5。"""
        from app.services.debug import MAX_ACTIVE_SESSIONS
        assert MAX_ACTIVE_SESSIONS == 5


# ---------------------------------------------------------------------------
# _sync_controller_state helper 测试
# ---------------------------------------------------------------------------

class TestSyncControllerState:
    """_sync_controller_state 辅助函数测试。"""

    @patch("app.services.debug.update_session_state", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_sync_with_pause_context(self, mock_update: AsyncMock) -> None:
        """有 pause_context 时正确同步。"""
        from app.api.debug import _sync_controller_state

        ctrl = _make_controller_mock()
        ctrl.pause_context = _make_pause_context_mock(turn=3, agent_name="sub-agent")
        session = _make_debug_session_mock()
        mock_update.return_value = session

        result = await _sync_controller_state(MagicMock(), uuid.uuid4(), ctrl)
        assert result is not None
        call_kwargs = mock_update.call_args
        assert call_kwargs.kwargs["current_turn"] == 3
        assert call_kwargs.kwargs["current_agent_name"] == "sub-agent"

    @patch("app.services.debug.update_session_state", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_sync_without_pause_context(self, mock_update: AsyncMock) -> None:
        """无 pause_context 时使用默认值。"""
        from app.api.debug import _sync_controller_state

        ctrl = _make_controller_mock()
        ctrl.pause_context = None
        session = _make_debug_session_mock()
        mock_update.return_value = session

        await _sync_controller_state(MagicMock(), uuid.uuid4(), ctrl)
        call_kwargs = mock_update.call_args
        assert call_kwargs.kwargs["current_turn"] == 0
        assert call_kwargs.kwargs["current_agent_name"] == ""
        assert call_kwargs.kwargs["pause_context"] == {}


# ---------------------------------------------------------------------------
# ORM 模型测试
# ---------------------------------------------------------------------------

class TestDebugSessionModel:
    """DebugSession ORM 模型测试。"""

    def test_tablename(self) -> None:
        """表名正确。"""
        from app.models.debug_session import DebugSession
        assert DebugSession.__tablename__ == "debug_sessions"

    def test_model_columns(self) -> None:
        """关键字段存在。"""
        from app.models.debug_session import DebugSession
        columns = {c.name for c in DebugSession.__table__.columns}
        expected = {
            "id", "agent_id", "agent_name", "user_id", "state", "mode",
            "input_message", "current_turn", "current_agent_name",
            "pause_context", "token_usage", "result", "error",
            "created_at", "updated_at", "finished_at",
        }
        assert expected.issubset(columns)

    def test_model_indexes(self) -> None:
        """索引字段存在。"""
        from app.models.debug_session import DebugSession
        indexed_cols = set()
        for col in DebugSession.__table__.columns:
            if col.index:
                indexed_cols.add(col.name)
        assert "agent_id" in indexed_cols
        assert "user_id" in indexed_cols
        assert "agent_name" in indexed_cols
