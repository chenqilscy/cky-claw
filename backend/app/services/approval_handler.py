"""HttpApprovalHandler — 基于 DB + 进程内事件的审批处理器。

实现 Framework 的 ApprovalHandler 接口，对接 CkyClaw Backend：
1. 创建 approval_request 记录（持久化）
2. 通过 ApprovalManager 等待审批结果
3. 返回 ApprovalDecision
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC
from typing import TYPE_CHECKING, Any

from app.core.database import async_session_factory
from app.models.approval import ApprovalRequest
from app.services.approval_manager import ApprovalManager
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext

logger = logging.getLogger(__name__)


class HttpApprovalHandler(ApprovalHandler):  # type: ignore[misc]
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

        # 1.5. 发布 Redis 事件（非阻塞，失败不影响审批流程）
        from app.api.ws import publish_approval_event

        await publish_approval_event("approval_created", {
            "id": str(approval_id),
            "session_id": self._session_id,
            "run_id": self._run_id,
            "agent_name": self._agent_name,
            "trigger": action_type,
            "content": action_detail,
            "status": "pending",
        })

        # 1.6. 通过 IM 渠道发送审批通知（非阻塞）
        try:
            from app.services.approval_notifier import notify_approval_via_im

            async with async_session_factory() as notify_db:
                await notify_approval_via_im(
                    notify_db,
                    agent_name=self._agent_name,
                    trigger=action_type,
                    content=action_detail,
                    approval_id=str(approval_id),
                )
        except Exception:
            logger.exception("IM 审批通知发送失败（不影响审批流程）")

        # 2. 注册事件 & 等待
        manager.register(approval_id)
        decision = await manager.wait_for_decision(approval_id, timeout=timeout)

        # 3. 更新 DB 记录
        from datetime import datetime

        from sqlalchemy import select

        status_map = {
            ApprovalDecision.APPROVED: "approved",
            ApprovalDecision.REJECTED: "rejected",
            ApprovalDecision.TIMEOUT: "timeout",
        }
        async with async_session_factory() as db:
            stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            db_record = (await db.execute(stmt)).scalar_one_or_none()
            if db_record and db_record.status == "pending":
                # 仅在 API 端尚未更新时由 handler 更新（超时场景）
                db_record.status = status_map.get(decision, "timeout")
                db_record.resolved_at = datetime.now(UTC)
                await db.commit()

        logger.info("Approval %s resolved: %s", approval_id, decision.value)
        return decision
