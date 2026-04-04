"""Workflow 工作流管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowValidateResponse,
)
from app.services import workflow as workflow_service

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """创建工作流定义。"""
    record = await workflow_service.create_workflow(db, data)
    return WorkflowResponse.model_validate(record)


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db),
) -> WorkflowListResponse:
    """查询工作流列表。"""
    rows, total = await workflow_service.list_workflows(db, limit=limit, offset=offset)
    return WorkflowListResponse(
        items=[WorkflowResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """获取单个工作流。"""
    record = await workflow_service.get_workflow(db, workflow_id)
    return WorkflowResponse.model_validate(record)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """更新工作流。"""
    record = await workflow_service.update_workflow(db, workflow_id, data)
    return WorkflowResponse.model_validate(record)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除工作流。"""
    await workflow_service.delete_workflow(db, workflow_id)


@router.post("/validate", response_model=WorkflowValidateResponse)
async def validate_workflow(
    data: WorkflowCreate,
) -> WorkflowValidateResponse:
    """验证工作流定义（不创建）。"""
    steps = [s.model_dump() for s in data.steps]
    edges = [e.model_dump() for e in data.edges]
    errors = workflow_service.validate_workflow_definition(steps, edges)
    return WorkflowValidateResponse(valid=len(errors) == 0, errors=errors)
