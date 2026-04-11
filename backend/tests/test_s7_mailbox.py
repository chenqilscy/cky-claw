"""S7 智能编排 — Backend 测试。

覆盖：
- Mailbox API 端点（发送/接收/标记已读/对话/删除）
- Mailbox Schema 校验
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ===========================================================================
# Mailbox API 测试
# ===========================================================================


class TestMailboxSendAPI:
    """POST /api/v1/mailbox/send 端点。"""

    @pytest.mark.anyio()
    async def test_send_message(self) -> None:
        """发送消息成功。"""
        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.run_id = "run-1"
        mock_record.from_agent = "agent-a"
        mock_record.to_agent = "agent-b"
        mock_record.content = "hello"
        mock_record.message_type = "handoff"
        mock_record.is_read = False
        mock_record.metadata_ = {}
        mock_record.created_at = "2025-01-01T00:00:00+00:00"

        with patch(
            "app.services.mailbox.send_message",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/mailbox/send",
                    json={
                        "run_id": "run-1",
                        "from_agent": "agent-a",
                        "to_agent": "agent-b",
                        "content": "hello",
                    },
                )
            assert resp.status_code == 201
            data = resp.json()
            assert data["from_agent"] == "agent-a"
            assert data["content"] == "hello"


class TestMailboxReceiveAPI:
    """GET /api/v1/mailbox/receive 端点。"""

    @pytest.mark.anyio()
    async def test_receive_messages(self) -> None:
        """接收消息列表。"""
        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.run_id = "run-1"
        mock_record.from_agent = "agent-a"
        mock_record.to_agent = "agent-b"
        mock_record.content = "hi"
        mock_record.message_type = "handoff"
        mock_record.is_read = False
        mock_record.metadata_ = {}
        mock_record.created_at = "2025-01-01T00:00:00+00:00"

        with patch(
            "app.services.mailbox.receive_messages",
            new_callable=AsyncMock,
            return_value=[mock_record],
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/mailbox/receive",
                    params={"agent_name": "agent-b"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["data"][0]["to_agent"] == "agent-b"

    @pytest.mark.anyio()
    async def test_receive_empty(self) -> None:
        """无消息时返回空列表。"""
        with patch(
            "app.services.mailbox.receive_messages",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/mailbox/receive",
                    params={"agent_name": "nobody"},
                )
            assert resp.status_code == 200
            assert resp.json()["total"] == 0


class TestMailboxMarkReadAPI:
    """POST /api/v1/mailbox/{message_id}/read 端点。"""

    @pytest.mark.anyio()
    async def test_mark_read(self) -> None:
        """标记已读成功。"""
        msg_id = uuid.uuid4()
        with patch(
            "app.services.mailbox.mark_read",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/api/v1/mailbox/{msg_id}/read")
            assert resp.status_code == 200
            assert "已读" in resp.json()["message"]


class TestMailboxConversationAPI:
    """GET /api/v1/mailbox/conversation 端点。"""

    @pytest.mark.anyio()
    async def test_conversation(self) -> None:
        """获取对话历史。"""
        with patch(
            "app.services.mailbox.get_conversation",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/mailbox/conversation",
                    params={"run_id": "r1", "agent_a": "a1", "agent_b": "a2"},
                )
            assert resp.status_code == 200
            assert resp.json()["total"] == 0


class TestMailboxDeleteAPI:
    """DELETE /api/v1/mailbox/runs/{run_id} 端点。"""

    @pytest.mark.anyio()
    async def test_delete_run_messages(self) -> None:
        """删除 Run 消息。"""
        with patch(
            "app.services.mailbox.delete_run_messages",
            new_callable=AsyncMock,
            return_value=3,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.delete("/api/v1/mailbox/runs/run-1")
            assert resp.status_code == 200
            assert resp.json()["deleted"] == 3


# ===========================================================================
# Schema 校验
# ===========================================================================


class TestMailboxSchemas:
    """Mailbox Schema 校验。"""

    def test_send_request_valid(self) -> None:
        """有效发送请求。"""
        from app.schemas.mailbox import MailboxSendRequest

        req = MailboxSendRequest(
            run_id="r1",
            from_agent="a",
            to_agent="b",
            content="hello",
        )
        assert req.message_type == "handoff"
        assert req.metadata == {}

    def test_send_request_custom_type(self) -> None:
        """自定义消息类型。"""
        from app.schemas.mailbox import MailboxSendRequest

        req = MailboxSendRequest(
            run_id="r1",
            from_agent="a",
            to_agent="b",
            content="check this",
            message_type="notification",
        )
        assert req.message_type == "notification"

    def test_list_response(self) -> None:
        """列表响应结构。"""
        from app.schemas.mailbox import MailboxListResponse

        resp = MailboxListResponse(data=[], total=0)
        assert resp.total == 0
        assert resp.data == []
