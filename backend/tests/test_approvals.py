"""Approval 审批请求测试。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ═══════════════════════════════════════════════════════════════════
# Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


def _make_approval_request(**overrides: Any) -> MagicMock:
    """构造模拟 ApprovalRequest ORM 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "run_id": str(uuid.uuid4()),
        "agent_name": "test-agent",
        "trigger": "tool_call",
        "content": {"tool_name": "get_weather", "arguments": {"city": "北京"}},
        "status": "pending",
        "comment": "",
        "resolved_at": None,
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


_DB_DEP = "app.core.deps.get_db"  # noqa: F841 — kept for reference
client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestApprovalSchemas:
    """Approval Schema 验证。"""

    def test_resolve_request_valid(self) -> None:
        from app.schemas.approval import ApprovalResolveRequest

        req = ApprovalResolveRequest(action="approve", comment="同意")
        assert req.action == "approve"
        assert req.comment == "同意"

    def test_resolve_request_reject(self) -> None:
        from app.schemas.approval import ApprovalResolveRequest

        req = ApprovalResolveRequest(action="reject")
        assert req.action == "reject"

    def test_resolve_request_invalid_action(self) -> None:
        from pydantic import ValidationError as PydanticValidationError

        from app.schemas.approval import ApprovalResolveRequest

        with pytest.raises(PydanticValidationError):
            ApprovalResolveRequest(action="cancel")

    def test_response_validate(self) -> None:
        from app.schemas.approval import ApprovalResponse

        mock = _make_approval_request()
        resp = ApprovalResponse.model_validate(mock, from_attributes=True)
        assert resp.id == mock.id
        assert resp.status == "pending"
        assert resp.agent_name == "test-agent"

    def test_list_response(self) -> None:
        from app.schemas.approval import ApprovalListResponse, ApprovalResponse

        mock = _make_approval_request()
        resp = ApprovalResponse.model_validate(mock, from_attributes=True)
        lr = ApprovalListResponse(data=[resp], total=1)
        assert lr.total == 1
        assert len(lr.data) == 1


# ═══════════════════════════════════════════════════════════════════
# API 测试
# ═══════════════════════════════════════════════════════════════════


class TestApprovalAPI:
    """Approval API 端点测试。"""

    @patch("app.api.approvals.approval_service")
    def test_list_empty(self, mock_svc: MagicMock) -> None:
        mock_svc.list_approval_requests = AsyncMock(return_value=([], 0))
        resp = client.get("/api/v1/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["data"] == []

    @patch("app.api.approvals.approval_service")
    def test_list_with_data(self, mock_svc: MagicMock) -> None:
        mock_item = _make_approval_request()
        mock_svc.list_approval_requests = AsyncMock(return_value=([mock_item], 1))
        resp = client.get("/api/v1/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["agent_name"] == "test-agent"

    @patch("app.api.approvals.approval_service")
    def test_list_with_status_filter(self, mock_svc: MagicMock) -> None:
        mock_svc.list_approval_requests = AsyncMock(return_value=([], 0))
        resp = client.get("/api/v1/approvals?status=pending")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_approval_requests.call_args
        assert call_kwargs.kwargs["status"] == "pending"

    @patch("app.api.approvals.approval_service")
    def test_get_approval(self, mock_svc: MagicMock) -> None:
        mock_item = _make_approval_request()
        mock_svc.get_approval_request = AsyncMock(return_value=mock_item)
        resp = client.get(f"/api/v1/approvals/{mock_item.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    @patch("app.api.approvals.approval_service")
    def test_get_approval_not_found(self, mock_svc: MagicMock) -> None:
        from app.core.exceptions import NotFoundError

        mock_svc.get_approval_request = AsyncMock(side_effect=NotFoundError("不存在"))
        resp = client.get(f"/api/v1/approvals/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.approvals.approval_service")
    def test_resolve_approve(self, mock_svc: MagicMock) -> None:
        resolved_item = _make_approval_request(
            status="approved",
            comment="同意",
            resolved_at=datetime.now(UTC),
        )
        mock_svc.resolve_approval_request = AsyncMock(return_value=resolved_item)
        resp = client.post(
            f"/api/v1/approvals/{resolved_item.id}/resolve",
            json={"action": "approve", "comment": "同意"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    @patch("app.api.approvals.approval_service")
    def test_resolve_reject(self, mock_svc: MagicMock) -> None:
        resolved_item = _make_approval_request(
            status="rejected",
            comment="拒绝",
            resolved_at=datetime.now(UTC),
        )
        mock_svc.resolve_approval_request = AsyncMock(return_value=resolved_item)
        resp = client.post(
            f"/api/v1/approvals/{resolved_item.id}/resolve",
            json={"action": "reject", "comment": "拒绝"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    @patch("app.api.approvals.approval_service")
    def test_resolve_already_resolved(self, mock_svc: MagicMock) -> None:
        from app.core.exceptions import ValidationError

        mock_svc.resolve_approval_request = AsyncMock(
            side_effect=ValidationError("审批请求已处理")
        )
        resp = client.post(
            f"/api/v1/approvals/{uuid.uuid4()}/resolve",
            json={"action": "approve"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# ApprovalManager 测试
# ═══════════════════════════════════════════════════════════════════


class TestApprovalManager:
    """ApprovalManager 单例 + 事件管理测试。"""

    def setup_method(self) -> None:
        from app.services.approval_manager import ApprovalManager

        ApprovalManager.reset()

    def test_singleton(self) -> None:
        from app.services.approval_manager import ApprovalManager

        m1 = ApprovalManager.get_instance()
        m2 = ApprovalManager.get_instance()
        assert m1 is m2

    def test_reset(self) -> None:
        from app.services.approval_manager import ApprovalManager

        m1 = ApprovalManager.get_instance()
        ApprovalManager.reset()
        m2 = ApprovalManager.get_instance()
        assert m1 is not m2

    @pytest.mark.asyncio
    async def test_register_and_resolve(self) -> None:
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        mgr = ApprovalManager.get_instance()
        aid = uuid.uuid4()
        mgr.register(aid)
        assert mgr.pending_count == 1

        # 在另一个 task 中 resolve
        async def do_resolve():
            await asyncio.sleep(0.01)
            mgr.resolve(aid, ApprovalDecision.APPROVED)

        asyncio.create_task(do_resolve())
        decision = await mgr.wait_for_decision(aid, timeout=5)
        assert decision == ApprovalDecision.APPROVED
        assert mgr.pending_count == 0

    @pytest.mark.asyncio
    async def test_resolve_rejected(self) -> None:
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        mgr = ApprovalManager.get_instance()
        aid = uuid.uuid4()
        mgr.register(aid)

        async def do_resolve():
            await asyncio.sleep(0.01)
            mgr.resolve(aid, ApprovalDecision.REJECTED)

        asyncio.create_task(do_resolve())
        decision = await mgr.wait_for_decision(aid, timeout=5)
        assert decision == ApprovalDecision.REJECTED

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        mgr = ApprovalManager.get_instance()
        aid = uuid.uuid4()
        mgr.register(aid)
        # 极短超时
        decision = await mgr.wait_for_decision(aid, timeout=0)
        assert decision == ApprovalDecision.TIMEOUT

    @pytest.mark.asyncio
    async def test_wait_unregistered(self) -> None:
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        mgr = ApprovalManager.get_instance()
        decision = await mgr.wait_for_decision(uuid.uuid4(), timeout=1)
        assert decision == ApprovalDecision.TIMEOUT

    def test_resolve_unknown_returns_false(self) -> None:
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        mgr = ApprovalManager.get_instance()
        result = mgr.resolve(uuid.uuid4(), ApprovalDecision.APPROVED)
        assert result is False

    def test_cleanup(self) -> None:
        from app.services.approval_manager import ApprovalManager

        mgr = ApprovalManager.get_instance()
        aid = uuid.uuid4()
        mgr.register(aid)
        assert mgr.pending_count == 1
        mgr.cleanup(aid)
        assert mgr.pending_count == 0


# ═══════════════════════════════════════════════════════════════════
# HttpApprovalHandler 测试
# ═══════════════════════════════════════════════════════════════════


class TestHttpApprovalHandler:
    """HttpApprovalHandler 测试。"""

    def setup_method(self) -> None:
        from app.services.approval_manager import ApprovalManager

        ApprovalManager.reset()

    @pytest.mark.asyncio
    async def test_creates_db_record_and_waits(self) -> None:
        """验证 handler 创建 DB 记录并等待审批决策。"""
        from app.services.approval_handler import HttpApprovalHandler
        from app.services.approval_manager import ApprovalManager
        from kasaya.approval.mode import ApprovalDecision

        handler = HttpApprovalHandler(
            session_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            agent_name="test-agent",
        )

        # Mock DB sessions
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
        )

        mgr = ApprovalManager.get_instance()

        # 在审批开始后立刻 approve
        async def auto_approve():
            await asyncio.sleep(0.05)
            # 找到 pending 事件并 resolve
            for aid in list(mgr._pending.keys()):
                mgr.resolve(aid, ApprovalDecision.APPROVED)

        run_context = MagicMock()

        with patch("app.services.approval_handler.async_session_factory", return_value=mock_session), \
             patch("app.api.ws.get_redis", new_callable=AsyncMock):
            asyncio.create_task(auto_approve())
            decision = await handler.request_approval(
                run_context=run_context,
                action_type="tool_call",
                action_detail={"tool_name": "get_weather", "arguments": {"city": "北京"}},
                timeout=5,
            )

        assert decision == ApprovalDecision.APPROVED

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout(self) -> None:
        """验证超时返回 TIMEOUT。"""
        from app.services.approval_handler import HttpApprovalHandler
        from kasaya.approval.mode import ApprovalDecision

        handler = HttpApprovalHandler(
            session_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            agent_name="test-agent",
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
        )

        run_context = MagicMock()

        with patch("app.services.approval_handler.async_session_factory", return_value=mock_session), \
             patch("app.api.ws.get_redis", new_callable=AsyncMock):
            decision = await handler.request_approval(
                run_context=run_context,
                action_type="tool_call",
                action_detail={"tool_name": "dangerous_tool", "arguments": {}},
                timeout=0,
            )

        assert decision == ApprovalDecision.TIMEOUT


# ═══════════════════════════════════════════════════════════════════
# Runtime Bridge 测试
# ═══════════════════════════════════════════════════════════════════


class TestBuildAgentApprovalMode:
    """_build_agent_from_config 审批模式传递测试。"""

    def _make_agent_config(self, **overrides: Any) -> MagicMock:
        defaults = {
            "name": "test-agent",
            "description": "desc",
            "instructions": "inst",
            "model": "gpt-4",
            "model_settings": None,
            "guardrails": {},
            "approval_mode": "suggest",
        }
        defaults.update(overrides)
        mock = MagicMock()
        for k, v in defaults.items():
            setattr(mock, k, v)
        return mock

    def test_suggest_mode(self) -> None:
        from app.services.session import _build_agent_from_config
        from kasaya.approval.mode import ApprovalMode

        config = self._make_agent_config(approval_mode="suggest")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode == ApprovalMode.SUGGEST

    def test_auto_edit_mode(self) -> None:
        from app.services.session import _build_agent_from_config
        from kasaya.approval.mode import ApprovalMode

        config = self._make_agent_config(approval_mode="auto-edit")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode == ApprovalMode.AUTO_EDIT

    def test_full_auto_mode(self) -> None:
        from app.services.session import _build_agent_from_config
        from kasaya.approval.mode import ApprovalMode

        config = self._make_agent_config(approval_mode="full-auto")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode == ApprovalMode.FULL_AUTO

    def test_unknown_mode_defaults_to_none(self) -> None:
        from app.services.session import _build_agent_from_config

        config = self._make_agent_config(approval_mode="unknown")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode is None


# ═══════════════════════════════════════════════════════════════════
# 路由注册测试
# ═══════════════════════════════════════════════════════════════════


class TestApprovalRouteRegistration:
    """验证审批 API 路由已注册。"""

    def test_routes_registered(self) -> None:
        routes = [r.path for r in app.routes]
        assert "/api/v1/approvals" in routes
        assert "/api/v1/approvals/{approval_id}" in routes
        assert "/api/v1/approvals/{approval_id}/resolve" in routes


# ═══════════════════════════════════════════════════════════════════
# Service 验证测试
# ═══════════════════════════════════════════════════════════════════


class TestApprovalServiceValidation:
    """Approval Service 参数校验。"""

    @pytest.mark.asyncio
    async def test_invalid_status_filter(self) -> None:
        from app.core.exceptions import ValidationError
        from app.services.approval import list_approval_requests

        mock_db = AsyncMock()
        with pytest.raises(ValidationError):
            await list_approval_requests(mock_db, status="invalid")

    @pytest.mark.asyncio
    async def test_invalid_action(self) -> None:
        from app.core.exceptions import ValidationError
        from app.services.approval import resolve_approval_request

        mock_db = AsyncMock()
        with pytest.raises(ValidationError):
            await resolve_approval_request(mock_db, uuid.uuid4(), action="cancel")

    @pytest.mark.asyncio
    async def test_resolve_already_resolved(self) -> None:
        from app.core.exceptions import ValidationError
        from app.services.approval import resolve_approval_request

        mock_item = _make_approval_request(status="approved")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_item))
        )
        with pytest.raises(ValidationError, match="已处理"):
            await resolve_approval_request(mock_db, mock_item.id, action="approve")

    @pytest.mark.asyncio
    async def test_resolve_not_found(self) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.approval import resolve_approval_request

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        with pytest.raises(NotFoundError):
            await resolve_approval_request(mock_db, uuid.uuid4(), action="approve")


# ═══════════════════════════════════════════════════════════════════
# IM 审批通知 (ApprovalNotifier) 测试
# ═══════════════════════════════════════════════════════════════════


def _make_im_channel(**overrides: Any) -> MagicMock:
    """构造模拟 IMChannel ORM 对象。"""
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-wecom",
        "channel_type": "wecom",
        "is_enabled": True,
        "is_deleted": False,
        "notify_approvals": True,
        "approval_recipient_id": "user001",
        "app_config": {"corpid": "corp1", "corpsecret": "sec", "token": "tok", "encoding_aes_key": "key", "agent_id": "100"},
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestApprovalNotifier:
    """IM 审批通知服务单元测试。"""

    def test_format_message_basic(self) -> None:
        """基本消息格式化。"""
        from app.services.approval_notifier import _format_approval_message

        msg = _format_approval_message(
            agent_name="my-agent",
            trigger="tool_call",
            content={"tool_name": "send_email", "arguments": {"to": "a@b.com"}},
            approval_id="abc-123",
        )
        assert "Kasaya 审批通知" in msg
        assert "my-agent" in msg
        assert "send_email" in msg
        assert "abc-123" in msg
        assert "tool_call" in msg

    def test_format_message_long_arguments(self) -> None:
        """超长参数截断。"""
        from app.services.approval_notifier import _format_approval_message

        long_args = {"data": "x" * 300}
        msg = _format_approval_message(
            agent_name="a", trigger="tool_call",
            content={"tool_name": "t", "arguments": long_args},
            approval_id="id1",
        )
        assert "..." in msg

    def test_format_message_no_tool_name(self) -> None:
        """content 中无 tool_name 时显示未知工具。"""
        from app.services.approval_notifier import _format_approval_message

        msg = _format_approval_message(
            agent_name="a", trigger="output",
            content={},
            approval_id="id2",
        )
        assert "未知工具" in msg

    @pytest.mark.asyncio
    async def test_notify_no_channels(self) -> None:
        """无启用审批通知的渠道时返回 0。"""
        from app.services.approval_notifier import notify_approval_via_im

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        count = await notify_approval_via_im(
            mock_db,
            agent_name="a", trigger="tool_call",
            content={"tool_name": "t"}, approval_id="id1",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_notify_single_channel_success(self) -> None:
        """单渠道成功发送。"""
        from app.services.approval_notifier import notify_approval_via_im

        channel = _make_im_channel()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[channel]))))
        )

        mock_adapter = AsyncMock()
        mock_adapter.send_message = AsyncMock(return_value=True)

        with patch("app.services.approval_notifier.get_adapter", return_value=mock_adapter):
            count = await notify_approval_via_im(
                mock_db,
                agent_name="test-agent", trigger="tool_call",
                content={"tool_name": "exec_cmd", "arguments": {"cmd": "ls"}},
                approval_id="ap-001",
            )
        assert count == 1
        mock_adapter.send_message.assert_awaited_once()
        call_args = mock_adapter.send_message.call_args
        assert call_args[0][1] == "user001"  # recipient_id
        assert "Kasaya 审批通知" in call_args[0][2]  # message content

    @pytest.mark.asyncio
    async def test_notify_send_failure(self) -> None:
        """发送失败不抛异常，返回 0。"""
        from app.services.approval_notifier import notify_approval_via_im

        channel = _make_im_channel()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[channel]))))
        )

        mock_adapter = AsyncMock()
        mock_adapter.send_message = AsyncMock(side_effect=Exception("network error"))

        with patch("app.services.approval_notifier.get_adapter", return_value=mock_adapter):
            count = await notify_approval_via_im(
                mock_db,
                agent_name="a", trigger="tool_call",
                content={"tool_name": "t"}, approval_id="id1",
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_notify_no_recipient_id(self) -> None:
        """未配置 recipient_id 的渠道跳过。"""
        from app.services.approval_notifier import notify_approval_via_im

        channel = _make_im_channel(approval_recipient_id=None)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[channel]))))
        )
        count = await notify_approval_via_im(
            mock_db,
            agent_name="a", trigger="tool_call",
            content={"tool_name": "t"}, approval_id="id1",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_notify_unknown_adapter(self) -> None:
        """未知 channel_type 跳过。"""
        from app.services.approval_notifier import notify_approval_via_im

        channel = _make_im_channel(channel_type="unknown_platform")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[channel]))))
        )

        with patch("app.services.approval_notifier.get_adapter", return_value=None):
            count = await notify_approval_via_im(
                mock_db,
                agent_name="a", trigger="tool_call",
                content={"tool_name": "t"}, approval_id="id1",
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_notify_multiple_channels(self) -> None:
        """多渠道并发通知。"""
        from app.services.approval_notifier import notify_approval_via_im

        ch1 = _make_im_channel(name="wecom-1", approval_recipient_id="u1")
        ch2 = _make_im_channel(name="dingtalk-1", channel_type="dingtalk", approval_recipient_id="u2")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ch1, ch2]))))
        )

        mock_adapter = AsyncMock()
        mock_adapter.send_message = AsyncMock(return_value=True)

        with patch("app.services.approval_notifier.get_adapter", return_value=mock_adapter):
            count = await notify_approval_via_im(
                mock_db,
                agent_name="a", trigger="tool_call",
                content={"tool_name": "t"}, approval_id="id1",
            )
        assert count == 2
        assert mock_adapter.send_message.await_count == 2

    @pytest.mark.asyncio
    async def test_notify_partial_failure(self) -> None:
        """部分渠道失败、部分成功。"""
        from app.services.approval_notifier import notify_approval_via_im

        ch1 = _make_im_channel(name="ok-channel", approval_recipient_id="u1")
        ch2 = _make_im_channel(name="fail-channel", approval_recipient_id="u2")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ch1, ch2]))))
        )

        mock_adapter = AsyncMock()
        mock_adapter.send_message = AsyncMock(side_effect=[True, False])

        with patch("app.services.approval_notifier.get_adapter", return_value=mock_adapter):
            count = await notify_approval_via_im(
                mock_db,
                agent_name="a", trigger="tool_call",
                content={"tool_name": "t"}, approval_id="id1",
            )
        assert count == 1


class TestIMChannelApprovalSchema:
    """IMChannel Schema 审批通知字段。"""

    def test_create_default_notify_false(self) -> None:
        """创建 Schema 默认 notify_approvals=False。"""
        from app.schemas.im_channel import IMChannelCreate

        ch = IMChannelCreate(name="test", channel_type="wecom")
        assert ch.notify_approvals is False
        assert ch.approval_recipient_id is None

    def test_create_with_notify(self) -> None:
        """创建 Schema 可设置 notify_approvals=True。"""
        from app.schemas.im_channel import IMChannelCreate

        ch = IMChannelCreate(
            name="test", channel_type="wecom",
            notify_approvals=True, approval_recipient_id="admin-001",
        )
        assert ch.notify_approvals is True
        assert ch.approval_recipient_id == "admin-001"

    def test_update_notify_fields(self) -> None:
        """更新 Schema 可设置审批通知字段。"""
        from app.schemas.im_channel import IMChannelUpdate

        upd = IMChannelUpdate(notify_approvals=True, approval_recipient_id="u123")
        assert upd.notify_approvals is True
        assert upd.approval_recipient_id == "u123"

    def test_response_includes_notify_fields(self) -> None:
        """响应 Schema 包含审批通知字段。"""
        from app.schemas.im_channel import IMChannelResponse

        mock = _make_im_channel(
            description="测试渠道",
            webhook_url=None, webhook_secret=None,
            agent_id=None, org_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        resp = IMChannelResponse.model_validate(mock, from_attributes=True)
        assert resp.notify_approvals is True
        assert resp.approval_recipient_id == "user001"
