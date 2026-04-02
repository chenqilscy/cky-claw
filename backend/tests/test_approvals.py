"""Approval 审批请求测试。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)
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
        lr = ApprovalListResponse(items=[resp], total=1)
        assert lr.total == 1
        assert len(lr.items) == 1


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
        assert data["items"] == []

    @patch("app.api.approvals.approval_service")
    def test_list_with_data(self, mock_svc: MagicMock) -> None:
        mock_item = _make_approval_request()
        mock_svc.list_approval_requests = AsyncMock(return_value=([mock_item], 1))
        resp = client.get("/api/v1/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["agent_name"] == "test-agent"

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
            resolved_at=datetime.now(timezone.utc),
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
            resolved_at=datetime.now(timezone.utc),
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
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_manager import ApprovalManager

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
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_manager import ApprovalManager

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
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_manager import ApprovalManager

        mgr = ApprovalManager.get_instance()
        aid = uuid.uuid4()
        mgr.register(aid)
        # 极短超时
        decision = await mgr.wait_for_decision(aid, timeout=0)
        assert decision == ApprovalDecision.TIMEOUT

    @pytest.mark.asyncio
    async def test_wait_unregistered(self) -> None:
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_manager import ApprovalManager

        mgr = ApprovalManager.get_instance()
        decision = await mgr.wait_for_decision(uuid.uuid4(), timeout=1)
        assert decision == ApprovalDecision.TIMEOUT

    def test_resolve_unknown_returns_false(self) -> None:
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_manager import ApprovalManager

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
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_handler import HttpApprovalHandler
        from app.services.approval_manager import ApprovalManager

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

        with patch("app.services.approval_handler.async_session_factory", return_value=mock_session):
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
        from ckyclaw_framework.approval.mode import ApprovalDecision

        from app.services.approval_handler import HttpApprovalHandler

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

        with patch("app.services.approval_handler.async_session_factory", return_value=mock_session):
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
        from ckyclaw_framework.approval.mode import ApprovalMode

        from app.services.session import _build_agent_from_config

        config = self._make_agent_config(approval_mode="suggest")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode == ApprovalMode.SUGGEST

    def test_auto_edit_mode(self) -> None:
        from ckyclaw_framework.approval.mode import ApprovalMode

        from app.services.session import _build_agent_from_config

        config = self._make_agent_config(approval_mode="auto-edit")
        agent = _build_agent_from_config(config)
        assert agent.approval_mode == ApprovalMode.AUTO_EDIT

    def test_full_auto_mode(self) -> None:
        from ckyclaw_framework.approval.mode import ApprovalMode

        from app.services.session import _build_agent_from_config

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
