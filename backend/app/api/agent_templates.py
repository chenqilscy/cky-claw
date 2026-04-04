"""Agent 模板管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent_template import (
    AgentTemplateCreate,
    AgentTemplateListResponse,
    AgentTemplateResponse,
    AgentTemplateUpdate,
    CreateAgentFromTemplate,
)
from app.services import agent_template as template_service

router = APIRouter(prefix="/api/v1/agent-templates", tags=["agent-templates"])


@router.post("", response_model=AgentTemplateResponse, status_code=201)
async def create_template(
    data: AgentTemplateCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentTemplateResponse:
    """创建 Agent 模板。"""
    record = await template_service.create_template(db, data)
    return AgentTemplateResponse.model_validate(record)


@router.get("", response_model=AgentTemplateListResponse)
async def list_templates(
    category: str | None = Query(None, description="按分类筛选"),
    is_builtin: bool | None = Query(None, description="是否内置"),
    limit: int = Query(50, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db),
) -> AgentTemplateListResponse:
    """查询模板列表。"""
    rows, total = await template_service.list_templates(
        db, category=category, is_builtin=is_builtin, limit=limit, offset=offset
    )
    return AgentTemplateListResponse(
        data=[AgentTemplateResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{template_id}", response_model=AgentTemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AgentTemplateResponse:
    """获取单个模板。"""
    record = await template_service.get_template(db, template_id)
    return AgentTemplateResponse.model_validate(record)


@router.put("/{template_id}", response_model=AgentTemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: AgentTemplateUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentTemplateResponse:
    """更新模板（内置模板不可编辑）。"""
    try:
        record = await template_service.update_template(db, template_id, data)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return AgentTemplateResponse.model_validate(record)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除模板（内置模板不可删除）。"""
    try:
        await template_service.delete_template(db, template_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/seed", response_model=dict)
async def seed_builtin_templates(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """初始化/同步内置模板（幂等操作）。"""
    created = await template_service.seed_builtin_templates(db)
    return {"created": created}
