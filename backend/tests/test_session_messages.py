"""Session 持久化测试 — SQLAlchemySessionBackend + GET /sessions/{id}/messages。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestSessionMessageSchemas:
    """SessionMessageItem / SessionMessagesResponse 模型测试。"""

    def test_session_message_item_valid(self) -> None:
        from app.schemas.session import SessionMessageItem

        item = SessionMessageItem(
            id=1,
            role="user",
            content="Hello",
            agent_name=None,
            tool_call_id=None,
            tool_calls=None,
            token_usage=None,
            created_at=datetime.now(timezone.utc),
        )
        assert item.role == "user"
        assert item.content == "Hello"
        assert item.id == 1

    def test_session_message_item_with_tool_calls(self) -> None:
        from app.schemas.session import SessionMessageItem

        item = SessionMessageItem(
            id=2,
            role="assistant",
            content="",
            agent_name="test-agent",
            tool_call_id=None,
            tool_calls=[{"id": "tc_1", "type": "function", "function": {"name": "foo", "arguments": "{}"}}],
            token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            created_at=datetime.now(timezone.utc),
        )
        assert item.tool_calls is not None
        assert len(item.tool_calls) == 1
        assert item.token_usage is not None

    def test_session_messages_response(self) -> None:
        from app.schemas.session import SessionMessageItem, SessionMessagesResponse

        now = datetime.now(timezone.utc)
        resp = SessionMessagesResponse(
            session_id="test-session-id",
            messages=[
                SessionMessageItem(id=1, role="user", content="hi", created_at=now),
                SessionMessageItem(id=2, role="assistant", content="hello", agent_name="bot", created_at=now),
            ],
            total=2,
        )
        assert resp.total == 2
        assert resp.session_id == "test-session-id"
        assert len(resp.messages) == 2


# ---------------------------------------------------------------------------
# SQLAlchemySessionBackend 单元测试
# ---------------------------------------------------------------------------


def _make_mock_db() -> AsyncMock:
    """创建 Mock AsyncSession。"""
    return AsyncMock()


class TestSQLAlchemySessionBackendLoad:
    """load() 方法测试。"""

    @pytest.mark.asyncio
    async def test_load_empty_returns_none(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        mock_db.execute.return_value = execute_result

        backend = SQLAlchemySessionBackend(mock_db)
        result = await backend.load("nonexistent-session")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_with_messages(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        now = datetime.now(timezone.utc)

        row1 = MagicMock()
        row1.role = "user"
        row1.content = "Hello"
        row1.agent_name = None
        row1.tool_call_id = None
        row1.tool_calls = None
        row1.token_usage = None
        row1.metadata_ = {}
        row1.created_at = now

        row2 = MagicMock()
        row2.role = "assistant"
        row2.content = "Hi there!"
        row2.agent_name = "test-agent"
        row2.tool_call_id = None
        row2.tool_calls = None
        row2.token_usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        row2.metadata_ = {}
        row2.created_at = now

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row1, row2]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        mock_db.execute.return_value = execute_result

        backend = SQLAlchemySessionBackend(mock_db)
        messages = await backend.load("session-123")

        assert messages is not None
        assert len(messages) == 2
        assert messages[0].role.value == "user"
        assert messages[1].role.value == "assistant"
        assert messages[1].token_usage is not None
        assert messages[1].token_usage.total_tokens == 8


class TestSQLAlchemySessionBackendSave:
    """save() 方法测试。"""

    @pytest.mark.asyncio
    async def test_save_empty_messages_is_noop(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        backend = SQLAlchemySessionBackend(mock_db)
        await backend.save("session-1", [])
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_creates_metadata_if_new(self) -> None:
        from ckyclaw_framework.model.message import Message, MessageRole

        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        mock_db.get.return_value = None  # 新 session，无 metadata

        backend = SQLAlchemySessionBackend(mock_db)
        msg = Message(role=MessageRole.USER, content="Hello")
        await backend.save("session-new", [msg])

        # 应该 add 了 SessionMessage + SessionMetadataRecord
        assert mock_db.add.call_count >= 2
        assert mock_db.flush.call_count == 2

    @pytest.mark.asyncio
    async def test_save_updates_existing_metadata(self) -> None:
        from ckyclaw_framework.model.message import Message, MessageRole

        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        existing_meta = MagicMock()
        existing_meta.message_count = 5
        existing_meta.last_agent = None
        mock_db.get.return_value = existing_meta

        backend = SQLAlchemySessionBackend(mock_db)
        msg = Message(role=MessageRole.ASSISTANT, content="Response", agent_name="bot")
        await backend.save("session-existing", [msg])

        assert existing_meta.message_count == 6
        assert existing_meta.last_agent == "bot"


class TestSQLAlchemySessionBackendDelete:
    """delete() 方法测试。"""

    @pytest.mark.asyncio
    async def test_delete_calls_db(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        backend = SQLAlchemySessionBackend(mock_db)
        await backend.delete("session-to-delete")
        assert mock_db.execute.call_count == 2
        assert mock_db.flush.call_count == 1


class TestSQLAlchemySessionBackendMetadata:
    """load_metadata / list_sessions 测试。"""

    @pytest.mark.asyncio
    async def test_load_metadata_not_found(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        mock_db.get.return_value = None

        backend = SQLAlchemySessionBackend(mock_db)
        result = await backend.load_metadata("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_metadata_found(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        now = datetime.now(timezone.utc)
        row = MagicMock()
        row.session_id = "session-1"
        row.created_at = now
        row.updated_at = now
        row.message_count = 10
        row.total_tokens = 500
        row.last_agent = "agent-x"
        row.extra = {}
        mock_db.get.return_value = row

        backend = SQLAlchemySessionBackend(mock_db)
        meta = await backend.load_metadata("session-1")
        assert meta is not None
        assert meta.session_id == "session-1"
        assert meta.message_count == 10
        assert meta.last_agent_name == "agent-x"

    @pytest.mark.asyncio
    async def test_list_sessions(self) -> None:
        from app.services.session_backend import SQLAlchemySessionBackend

        mock_db = AsyncMock()
        now = datetime.now(timezone.utc)
        row = MagicMock()
        row.session_id = "s1"
        row.created_at = now
        row.updated_at = now
        row.message_count = 3
        row.total_tokens = 100
        row.last_agent = "a"
        row.extra = {}

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        mock_db.execute.return_value = execute_result

        backend = SQLAlchemySessionBackend(mock_db)
        sessions = await backend.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].session_id == "s1"


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestGetSessionMessagesAPI:
    """GET /api/v1/sessions/{id}/messages 端点测试。"""

    @patch("app.api.sessions.session_service")
    def test_get_messages_success(self, mock_svc: MagicMock) -> None:
        now = datetime.now(timezone.utc)
        row1 = MagicMock()
        row1.id = 1
        row1.role = "user"
        row1.content = "Hello"
        row1.agent_name = None
        row1.tool_call_id = None
        row1.tool_calls = None
        row1.token_usage = None
        row1.created_at = now

        row2 = MagicMock()
        row2.id = 2
        row2.role = "assistant"
        row2.content = "Hi!"
        row2.agent_name = "test-bot"
        row2.tool_call_id = None
        row2.tool_calls = None
        row2.token_usage = None
        row2.created_at = now

        mock_svc.get_session_messages = AsyncMock(return_value=[row1, row2])

        client = TestClient(app)
        session_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/sessions/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["session_id"] == session_id
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["agent_name"] == "test-bot"

    @patch("app.api.sessions.session_service")
    def test_get_messages_empty(self, mock_svc: MagicMock) -> None:
        mock_svc.get_session_messages = AsyncMock(return_value=[])

        client = TestClient(app)
        session_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/sessions/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["messages"] == []

    @patch("app.api.sessions.session_service")
    def test_get_messages_session_not_found(self, mock_svc: MagicMock) -> None:
        from app.core.exceptions import NotFoundError

        mock_svc.get_session_messages = AsyncMock(side_effect=NotFoundError("Session not found"))

        client = TestClient(app)
        session_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/sessions/{session_id}/messages")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ORM Model 测试
# ---------------------------------------------------------------------------


class TestSessionMessageModel:
    """SessionMessage / SessionMetadataRecord ORM 模型测试。"""

    def test_session_message_tablename(self) -> None:
        from app.models.session_message import SessionMessage

        assert SessionMessage.__tablename__ == "session_messages"

    def test_session_metadata_tablename(self) -> None:
        from app.models.session_message import SessionMetadataRecord

        assert SessionMetadataRecord.__tablename__ == "session_metadata"

    def test_session_message_columns(self) -> None:
        from app.models.session_message import SessionMessage

        columns = {c.name for c in SessionMessage.__table__.columns}
        expected = {"id", "session_id", "role", "content", "agent_name", "tool_call_id", "tool_calls", "token_usage", "metadata_", "created_at"}
        assert expected.issubset(columns)

    def test_session_metadata_columns(self) -> None:
        from app.models.session_message import SessionMetadataRecord

        columns = {c.name for c in SessionMetadataRecord.__table__.columns}
        expected = {"session_id", "message_count", "total_tokens", "last_agent", "extra", "created_at", "updated_at"}
        assert expected.issubset(columns)


# ---------------------------------------------------------------------------
# 路由注册测试
# ---------------------------------------------------------------------------


class TestSessionMessagesRouteRegistration:
    """验证消息查询路由已注册。"""

    def test_messages_route_registered(self) -> None:
        routes = [r.path for r in app.routes]
        assert "/api/v1/sessions/{session_id}/messages" in routes
