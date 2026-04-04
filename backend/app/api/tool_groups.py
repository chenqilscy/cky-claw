"""Tool Group 管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import check_quota, get_org_id
from app.schemas.tool_group import (
    ToolGroupCreate,
    ToolGroupListResponse,
    ToolGroupResponse,
    ToolGroupUpdate,
)
from app.services import tool_group as tg_service

router = APIRouter(prefix="/api/v1/tool-groups", tags=["tool-groups"])


@router.get("", response_model=ToolGroupListResponse, dependencies=[Depends(require_permission("tool_groups", "read"))])
async def list_tool_groups(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ToolGroupListResponse:
    """获取工具组列表。"""
    groups, total = await tg_service.list_tool_groups(db, org_id=org_id)
    return ToolGroupListResponse(
        data=[ToolGroupResponse.model_validate(g) for g in groups],
        total=total,
    )


@router.get("/{name}", response_model=ToolGroupResponse, dependencies=[Depends(require_permission("tool_groups", "read"))])
async def get_tool_group(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> ToolGroupResponse:
    """获取工具组详情。"""
    tg = await tg_service.get_tool_group_by_name(db, name)
    return ToolGroupResponse.model_validate(tg)


@router.post("", response_model=ToolGroupResponse, status_code=201, dependencies=[Depends(require_permission("tool_groups", "write"))])
async def create_tool_group(
    data: ToolGroupCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ToolGroupResponse:
    """创建工具组。"""
    await check_quota(db, org_id, "max_tool_groups")
    tg = await tg_service.create_tool_group(db, data)
    return ToolGroupResponse.model_validate(tg)


@router.put("/{name}", response_model=ToolGroupResponse, dependencies=[Depends(require_permission("tool_groups", "write"))])
async def update_tool_group(
    name: str,
    data: ToolGroupUpdate,
    db: AsyncSession = Depends(get_db),
) -> ToolGroupResponse:
    """更新工具组。"""
    tg = await tg_service.update_tool_group(db, name, data)
    return ToolGroupResponse.model_validate(tg)


@router.delete("/{name}", status_code=204, dependencies=[Depends(require_permission("tool_groups", "delete"))])
async def delete_tool_group(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除工具组。"""
    await tg_service.delete_tool_group(db, name)
