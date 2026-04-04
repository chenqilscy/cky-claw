"""Agent 版本管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.schemas.agent_version import (
    AgentRollbackRequest,
    AgentVersionDiffResponse,
    AgentVersionListResponse,
    AgentVersionResponse,
)
from app.services import agent_version as version_service

router = APIRouter(prefix="/api/v1/agents", tags=["agent-versions"])


@router.get("/{agent_id}/versions", response_model=AgentVersionListResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def list_versions(
    agent_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> AgentVersionListResponse:
    """获取 Agent 版本列表。"""
    # 校验 Agent 存在
    await version_service.get_agent_by_id(db, agent_id)

    versions, total = await version_service.list_versions(
        db, agent_id, limit=limit, offset=offset
    )
    return AgentVersionListResponse(
        data=[AgentVersionResponse.model_validate(v) for v in versions],
        total=total,
    )


@router.get("/{agent_id}/versions/diff", response_model=AgentVersionDiffResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def diff_versions(
    agent_id: uuid.UUID,
    v1: int = Query(..., ge=1, description="版本 A"),
    v2: int = Query(..., ge=1, description="版本 B"),
    db: AsyncSession = Depends(get_db),
) -> AgentVersionDiffResponse:
    """对比两个版本的快照。"""
    await version_service.get_agent_by_id(db, agent_id)

    ver_a = await version_service.get_version(db, agent_id, v1)
    ver_b = await version_service.get_version(db, agent_id, v2)
    return AgentVersionDiffResponse(
        version_a=ver_a.version,
        version_b=ver_b.version,
        snapshot_a=ver_a.snapshot,
        snapshot_b=ver_b.snapshot,
    )


@router.get("/{agent_id}/versions/{version}", response_model=AgentVersionResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def get_version(
    agent_id: uuid.UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
) -> AgentVersionResponse:
    """获取指定版本详情。"""
    await version_service.get_agent_by_id(db, agent_id)

    ver = await version_service.get_version(db, agent_id, version)
    return AgentVersionResponse.model_validate(ver)


@router.post("/{agent_id}/versions/{version}/rollback", response_model=AgentVersionResponse, status_code=201, dependencies=[Depends(require_permission("agents", "write"))])
async def rollback_to_version(
    agent_id: uuid.UUID,
    version: int,
    body: AgentRollbackRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AgentVersionResponse:
    """回滚 Agent 到指定版本。"""
    agent = await version_service.get_agent_by_id(db, agent_id)

    change_summary = body.change_summary if body else None
    new_ver = await version_service.rollback_to_version(
        db, agent, version, change_summary=change_summary
    )
    return AgentVersionResponse.model_validate(new_ver)
