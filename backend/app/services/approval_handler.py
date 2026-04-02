"""HttpApprovalHandler — 基于 DB + 进程内事件的审批处理器。

实现 Framework 的 ApprovalHandler 接口，对接 CkyClaw Backend：
1. 创建 approval_request 记录（持久化）
2. 通过 ApprovalManager 等待审批结果
3. 返回 ApprovalDecision
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision
from ckyclaw_framework.runner.run_context import RunContext

from app.core.database import async_session_factory
from app.models.approval import ApprovalRequest
from app.services.approval_manager import ApprovalManager

logger = logging.getLogger(__name__)


class HttpApprovalHandler(ApprovalHandler):
    """HTTP/DB 驱动的审批处理器。

    在 Runner Agent Loop 内部被调用，使用独立 DB session（不复用 request-scoped session），
    通过 ApprovalManager 进程内事件等待人工审批结果。
    """

    def __init__(
        self,
        session_id: str,
        run_id: str,
        agent_name: str,
    ) -> None:
        self._session_id = session_id
        self._run_id = run_id
        self._agent_name = agent_name

    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        """发起审批请求，等待结果。

        1. 创建 DB 记录
        2. 注册进程内事件
        3. 等待决策（或超时）
        4. 更新 DB 记录状态
        """
        approval_id = uuid.uuid4()
        manager = ApprovalManager.get_instance()

        # 1. 创建 DB 记录（独立 session）
        async with async_session_factory() as db:
            record = ApprovalRequest(
                id=approval_id,
                session_id=uuid.UUID(self._session_id),
                run_id=self._run_id,
                agent_name=self._agent_name,
                trigger=action_type,
                content=action_detail,
                status="pending",
            )
            db.add(record)
            await db.commit()

        logger.info(
            "Approval request created: %s (agent=%s, trigger=%s, tool=%s)",
            approval_id,
            self._agent_name,
            action_type,
            action_detail.get("tool_name", "unknown"),
        )

        # 2. 注册事件 & 等待
        manager.register(approval_id)
        decision = await manager.wait_for_decision(approval_id, timeout=timeout)

        # 3. 更新 DB 记录
        from datetime import datetime, timezone

        from sqlalchemy import select

        status_map = {
            ApprovalDecision.APPROVED: "approved",
            ApprovalDecision.REJECTED: "rejected",
            ApprovalDecision.TIMEOUT: "timeout",
        }
        async with async_session_factory() as db:
            stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            record = (await db.execute(stmt)).scalar_one_or_none()
            if record and record.status == "pending":
                # 仅在 API 端尚未更新时由 handler 更新（超时场景）
                record.status = status_map.get(decision, "timeout")
                record.resolved_at = datetime.now(timezone.utc)
                await db.commit()

        logger.info("Approval %s resolved: %s", approval_id, decision.value)
        return decision
