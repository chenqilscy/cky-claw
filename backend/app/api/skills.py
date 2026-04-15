"""Skill 技能知识包管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import check_quota, get_org_id
from app.schemas.skill import (
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillSearchRequest,
    SkillUpdate,
)
from app.services import skill as skill_service

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.post(
    "",
    response_model=SkillResponse,
    status_code=201,
    dependencies=[Depends(require_permission("skills", "write"))],
)
async def create_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> SkillResponse:
    """创建技能知识包。"""
    await check_quota(db, org_id, "max_skills")
    record = await skill_service.create_skill(db, data)
    return SkillResponse.model_validate(record)


@router.get("", response_model=SkillListResponse, dependencies=[Depends(require_permission("skills", "read"))])
async def list_skills(
    category: str | None = Query(None, description="按分类筛选"),
    tag: str | None = Query(None, description="按标签筛选"),
    limit: int = Query(20, ge=1, le=200, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> SkillListResponse:
    """查询技能列表。"""
    rows, total = await skill_service.list_skills(
        db, category=category, tag=tag, limit=limit, offset=offset, org_id=org_id
    )
    return SkillListResponse(
        data=[SkillResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/for-agent/{agent_name}",
    response_model=list[SkillResponse],
    dependencies=[Depends(require_permission("skills", "read"))],
)
async def find_skills_for_agent(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
) -> list[SkillResponse]:
    """查找适用于指定 Agent 的技能。"""
    rows = await skill_service.find_skills_for_agent(db, agent_name)
    return [SkillResponse.model_validate(r) for r in rows]


@router.get("/{skill_id}", response_model=SkillResponse, dependencies=[Depends(require_permission("skills", "read"))])
async def get_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SkillResponse:
    """获取单个技能。"""
    record = await skill_service.get_skill(db, skill_id)
    return SkillResponse.model_validate(record)


@router.put("/{skill_id}", response_model=SkillResponse, dependencies=[Depends(require_permission("skills", "write"))])
async def update_skill(
    skill_id: uuid.UUID,
    data: SkillUpdate,
    db: AsyncSession = Depends(get_db),
) -> SkillResponse:
    """更新技能。"""
    record = await skill_service.update_skill(db, skill_id, data)
    return SkillResponse.model_validate(record)


@router.delete("/{skill_id}", status_code=204, dependencies=[Depends(require_permission("skills", "delete"))])
async def delete_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除技能。"""
    await skill_service.delete_skill(db, skill_id)


@router.post(
    "/search",
    response_model=list[SkillResponse],
    dependencies=[Depends(require_permission("skills", "read"))],
)
async def search_skills(
    data: SkillSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[SkillResponse]:
    """搜索技能。"""
    rows = await skill_service.search_skills(db, data)
    return [SkillResponse.model_validate(r) for r in rows]
