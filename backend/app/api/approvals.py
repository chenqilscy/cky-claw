"""Approval 审批请求 API。"""

from __future__ import annotations
import uuid

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_db, require_permission
from app.schemas.approval import ApprovalListResponse, ApprovalResolveRequest, ApprovalResponse
from app.services import approval as approval_service

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse, dependencies=[Depends(require_permission("approvals", "read"))])
async def list_approvals(
    status: str | None = Query(None, description="按状态过滤: pending/approved/rejected/timeout"),
    agent_name: str | None = Query(None, description="按 Agent 名称过滤"),
    session_id: uuid.UUID | None = Query(None, description="按 Session ID 过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ApprovalListResponse:
    """查询审批请求列表。"""
    items, total = await approval_service.list_approval_requests(
        db,
        status=status,
        agent_name=agent_name,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        data=[ApprovalResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_permission("approvals", "read"))],
)
async def get_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """获取审批请求详情。"""
    record = await approval_service.get_approval_request(db, approval_id)
    return ApprovalResponse.model_validate(record)


@router.post(
    "/{approval_id}/resolve",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_permission("approvals", "execute"))],
)
async def resolve_approval(
    approval_id: uuid.UUID,
    body: ApprovalResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """审批操作（approve/reject）。"""
    record = await approval_service.resolve_approval_request(
        db,
        approval_id,
        action=body.action,
        comment=body.comment,
    )
    return ApprovalResponse.model_validate(record)
