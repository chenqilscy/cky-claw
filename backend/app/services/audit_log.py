"""AuditLog 审计日志业务逻辑层。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.audit_log import AuditLog

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def create_audit_log(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    status_code: int | None = None,
) -> AuditLog:
    """写入一条审计日志。"""
    record = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        status_code=status_code,
    )
    db.add(record)
    await db.commit()
    return record


async def list_audit_logs(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    action: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    resource_id: str | None = None,
) -> tuple[list[AuditLog], int]:
    """查询审计日志列表（分页+过滤）。"""
    base_stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if action:
        base_stmt = base_stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        base_stmt = base_stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        base_stmt = base_stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if resource_id:
        base_stmt = base_stmt.where(AuditLog.resource_id == resource_id)
        count_stmt = count_stmt.where(AuditLog.resource_id == resource_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = base_stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_audit_log(db: AsyncSession, log_id: uuid.UUID) -> AuditLog | None:
    """获取单条审计日志。"""
    stmt = select(AuditLog).where(AuditLog.id == log_id)
    return (await db.execute(stmt)).scalar_one_or_none()
