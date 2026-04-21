"""Approval 审批请求业务逻辑层。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError, ValidationError
from app.models.approval import ApprovalRequest
from app.services.approval_manager import ApprovalManager
from kasaya.approval.mode import ApprovalDecision

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

VALID_STATUSES = {"pending", "approved", "rejected", "timeout"}
VALID_ACTIONS = {"approve", "reject"}


async def list_approval_requests(
    db: AsyncSession,
    *,
    status: str | None = None,
    agent_name: str | None = None,
    session_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ApprovalRequest], int]:
    """查询审批请求列表。"""
    base = select(ApprovalRequest)
    count_base = select(func.count()).select_from(ApprovalRequest)

    if status:
        if status not in VALID_STATUSES:
            raise ValidationError(f"status 必须是 {VALID_STATUSES} 之一")
        base = base.where(ApprovalRequest.status == status)
        count_base = count_base.where(ApprovalRequest.status == status)
    if agent_name:
        base = base.where(ApprovalRequest.agent_name == agent_name)
        count_base = count_base.where(ApprovalRequest.agent_name == agent_name)
    if session_id:
        base = base.where(ApprovalRequest.session_id == session_id)
        count_base = count_base.where(ApprovalRequest.session_id == session_id)

    total = (await db.execute(count_base)).scalar() or 0
    stmt = base.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def get_approval_request(
    db: AsyncSession,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    """获取单个审批请求详情。"""
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"审批请求 '{approval_id}' 不存在")
    return record


async def resolve_approval_request(
    db: AsyncSession,
    approval_id: uuid.UUID,
    *,
    action: str,
    comment: str = "",
) -> ApprovalRequest:
    """解决审批请求（approve/reject）。

    1. 校验请求存在且状态为 pending
    2. 更新 DB 记录
    3. 通知 ApprovalManager（触发 Runner 继续执行）
    """
    if action not in VALID_ACTIONS:
        raise ValidationError(f"action 必须是 {VALID_ACTIONS} 之一")

    record = await get_approval_request(db, approval_id)
    if record.status != "pending":
        raise ValidationError(f"审批请求已处理，当前状态: {record.status}")

    # 更新 DB 记录
    record.status = "approved" if action == "approve" else "rejected"
    record.comment = comment
    record.resolved_at = datetime.now(UTC)
    await db.flush()

    # 通知 ApprovalManager
    decision = ApprovalDecision.APPROVED if action == "approve" else ApprovalDecision.REJECTED
    manager = ApprovalManager.get_instance()
    resolved = manager.resolve(approval_id, decision)
    if not resolved:
        # 可能已超时或进程重启后丢失事件，仅做日志记录
        import logging
        logging.getLogger(__name__).warning(
            "Approval %s resolved in DB but no pending event found (may have timed out)", approval_id
        )

    await db.commit()
    await db.refresh(record)

    # 发布 Redis 事件（非阻塞，失败不影响审批流程）
    from app.api.ws import publish_approval_event

    await publish_approval_event("approval_resolved", {
        "id": str(approval_id),
        "status": record.status,
        "comment": record.comment,
    })

    return record
