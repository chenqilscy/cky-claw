"""Session & Run API 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.exceptions import NotFoundError
from app.main import app
from app.schemas.session import (
    MessageItem,
    RunConfig,
    RunRequest,
    RunResponse,
    SessionCreate,
    SessionResponse,
    TokenUsageResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_session_record(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "agent_name": "test-agent",
        "status": "active",
        "title": "",
        "metadata_": {},
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


class TestSessionSchemas:
    def test_session_create(self) -> None:
        data = SessionCreate(agent_name="my-agent")
        assert data.agent_name == "my-agent"
        assert data.metadata == {}

    def test_run_request_defaults(self) -> None:
        req = RunRequest(input="hello")
        assert req.config.stream is True
        assert req.config.max_turns == 10
        assert req.config.model_override is None

    def test_run_request_custom_config(self) -> None:
        req = RunRequest(input="hello", config=RunConfig(stream=False, max_turns=5))
        assert req.config.stream is False
        assert req.config.max_turns == 5

    def test_run_request_empty_input_rejected(self) -> None:
        with pytest.raises(ValueError):
            RunRequest(input="")

    def test_session_response_from_orm(self) -> None:
        mock = _make_session_record()
        resp = SessionResponse.model_validate(mock, from_attributes=True)
        assert resp.agent_name == "test-agent"
        assert resp.status == "active"

    def test_token_usage_response_defaults(self) -> None:
        t = TokenUsageResponse()
        assert t.total_tokens == 0


# ---------------------------------------------------------------------------
# Session CRUD API 测试
# ---------------------------------------------------------------------------


class TestSessionAPI:
    @patch("app.api.sessions.session_service")
    def test_create_session_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        session_mock = _make_session_record()
        mock_svc.create_session = AsyncMock(return_value=session_mock)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.post("/api/v1/sessions", json={"agent_name": "test-agent"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        assert resp.json()["agent_name"] == "test-agent"

    @patch("app.api.sessions.session_service")
    def test_create_session_agent_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.create_session = AsyncMock(side_effect=NotFoundError("Agent 'nope' 不存在"))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.post("/api/v1/sessions", json={"agent_name": "nope"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.sessions.session_service")
    def test_get_session_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        session_mock = _make_session_record()
        mock_svc.get_session = AsyncMock(return_value=session_mock)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/sessions/{session_mock.id}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @patch("app.api.sessions.session_service")
    def test_get_session_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        fake_id = uuid.uuid4()
        mock_svc.get_session = AsyncMock(side_effect=NotFoundError(f"Session '{fake_id}' 不存在"))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/sessions/{fake_id}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @patch("app.api.sessions.session_service")
    def test_list_sessions(self, mock_svc: MagicMock, client: TestClient) -> None:
        session_mock = _make_session_record()
        mock_svc.list_sessions = AsyncMock(return_value=([session_mock], 1))

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.get("/api/v1/sessions")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    @patch("app.api.sessions.session_service")
    def test_delete_session_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_session = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.delete(f"/api/v1/sessions/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["message"] == "Session 已删除"

    @patch("app.api.sessions.session_service")
    def test_run_non_stream(self, mock_svc: MagicMock, client: TestClient) -> None:
        run_resp = RunResponse(
            run_id=str(uuid.uuid4()),
            status="completed",
            output="Hello!",
            token_usage=TokenUsageResponse(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            duration_ms=1200,
            turn_count=1,
            last_agent_name="test-agent",
        )
        mock_svc.execute_run = AsyncMock(return_value=run_resp)

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.post(
                f"/api/v1/sessions/{uuid.uuid4()}/run",
                json={"input": "hello", "config": {"stream": False}},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["output"] == "Hello!"
        assert body["token_usage"]["total_tokens"] == 15

    @patch("app.api.sessions.session_service")
    def test_run_stream(self, mock_svc: MagicMock, client: TestClient) -> None:
        async def _mock_stream(*args, **kwargs):  # type: ignore[no-untyped-def]
            yield 'event: run_start\ndata: {"run_id": "abc"}\n\n'
            yield 'event: text_delta\ndata: {"delta": "Hi"}\n\n'
            yield 'event: run_end\ndata: {"status": "completed"}\n\n'

        mock_svc.execute_run_stream = _mock_stream

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        try:
            resp = client.post(
                f"/api/v1/sessions/{uuid.uuid4()}/run",
                json={"input": "hello", "config": {"stream": True}},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        assert "run_start" in body
        assert "text_delta" in body
        assert "run_end" in body


# ---------------------------------------------------------------------------
# 路由注册测试
# ---------------------------------------------------------------------------


class TestSessionRouteRegistration:
    def test_session_routes_registered(self) -> None:
        paths = [route.path for route in app.routes]
        assert "/api/v1/sessions" in paths
        assert "/api/v1/sessions/{session_id}" in paths
        assert "/api/v1/sessions/{session_id}/run" in paths
