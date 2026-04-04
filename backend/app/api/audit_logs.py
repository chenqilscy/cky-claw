"""AuditLog 审计日志 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.services import audit_log as audit_log_service

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    action: str | None = Query(None, max_length=32, description="操作类型过滤"),
    resource_type: str | None = Query(None, max_length=64, description="资源类型过滤"),
    user_id: str | None = Query(None, max_length=64, description="用户 ID 过滤"),
    resource_id: str | None = Query(None, max_length=128, description="资源 ID 过滤"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """查询审计日志列表。"""
    rows, total = await audit_log_service.list_audit_logs(
        db,
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        resource_id=resource_id,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """获取单条审计日志。"""
    record = await audit_log_service.get_audit_log(db, log_id)
    if record is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"审计日志 '{log_id}' 不存在")
    return AuditLogResponse.model_validate(record)
