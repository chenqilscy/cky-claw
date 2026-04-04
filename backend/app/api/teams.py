"""Team 团队管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant import check_quota, get_org_id
from app.schemas.team import (
    TeamConfigCreate,
    TeamConfigListResponse,
    TeamConfigResponse,
    TeamConfigUpdate,
)
from app.services import team as team_service

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=TeamConfigResponse, status_code=201)
async def create_team(
    data: TeamConfigCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> TeamConfigResponse:
    """创建团队配置。"""
    await check_quota(db, org_id, "max_teams")
    record = await team_service.create_team(db, data)
    return TeamConfigResponse.model_validate(record)


@router.get("", response_model=TeamConfigListResponse)
async def list_teams(
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    search: str | None = Query(None, max_length=64, description="名称搜索"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> TeamConfigListResponse:
    """查询团队配置列表。"""
    rows, total = await team_service.list_teams(db, limit=limit, offset=offset, search=search, org_id=org_id)
    return TeamConfigListResponse(
        data=[TeamConfigResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{team_id}", response_model=TeamConfigResponse)
async def get_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TeamConfigResponse:
    """获取单个团队配置。"""
    record = await team_service.get_team(db, team_id)
    return TeamConfigResponse.model_validate(record)


@router.put("/{team_id}", response_model=TeamConfigResponse)
async def update_team(
    team_id: uuid.UUID,
    data: TeamConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> TeamConfigResponse:
    """更新团队配置。"""
    record = await team_service.update_team(db, team_id, data)
    return TeamConfigResponse.model_validate(record)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除团队配置。"""
    await team_service.delete_team(db, team_id)
