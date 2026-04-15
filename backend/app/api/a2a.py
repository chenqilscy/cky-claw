"""A2A 协议 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import get_org_id
from app.schemas.a2a import (
    A2AAgentCardCreate,
    A2AAgentCardListResponse,
    A2AAgentCardResponse,
    A2AAgentCardUpdate,
    A2ADiscoveryResponse,
    A2ATaskCreate,
    A2ATaskListResponse,
    A2ATaskResponse,
)
from app.services import a2a as a2a_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/a2a", tags=["a2a"])


# ---------------------------------------------------------------------------
# Agent Card 端点
# ---------------------------------------------------------------------------
@router.post(
    "/agent-cards",
    response_model=A2AAgentCardResponse,
    status_code=201,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def create_agent_card(
    data: A2AAgentCardCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2AAgentCardResponse:
    """注册 Agent Card。"""
    row = await a2a_service.create_agent_card(db, data, org_id=org_id)
    return A2AAgentCardResponse.model_validate(row)


@router.get(
    "/agent-cards",
    response_model=A2AAgentCardListResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def list_agent_cards(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2AAgentCardListResponse:
    """查询 Agent Card 列表。"""
    rows, total = await a2a_service.list_agent_cards(db, limit=limit, offset=offset, org_id=org_id)
    return A2AAgentCardListResponse(
        data=[A2AAgentCardResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/agent-cards/{card_id}",
    response_model=A2AAgentCardResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def get_agent_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2AAgentCardResponse:
    """获取单个 Agent Card。"""
    row = await a2a_service.get_agent_card(db, card_id, org_id=org_id)
    return A2AAgentCardResponse.model_validate(row)


@router.put(
    "/agent-cards/{card_id}",
    response_model=A2AAgentCardResponse,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def update_agent_card(
    card_id: uuid.UUID,
    data: A2AAgentCardUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2AAgentCardResponse:
    """更新 Agent Card。"""
    row = await a2a_service.update_agent_card(db, card_id, data, org_id=org_id)
    return A2AAgentCardResponse.model_validate(row)


@router.delete(
    "/agent-cards/{card_id}",
    status_code=204,
    dependencies=[Depends(require_permission("agents", "delete"))],
)
async def delete_agent_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> None:
    """删除 Agent Card。"""
    await a2a_service.delete_agent_card(db, card_id, org_id=org_id)


@router.get(
    "/discover/{agent_id}",
    response_model=A2ADiscoveryResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def discover_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2ADiscoveryResponse:
    """通过 Agent ID 发现 Agent Card（服务发现 API）。"""
    row = await a2a_service.discover_agent_card(db, agent_id, org_id=org_id)
    return A2ADiscoveryResponse(
        name=row.name,
        description=row.description,
        url=row.url,
        version=row.version,
        capabilities=row.capabilities,
        skills=row.skills,
        authentication=row.authentication,
    )


# ---------------------------------------------------------------------------
# Task 端点
# ---------------------------------------------------------------------------
@router.post(
    "/tasks",
    response_model=A2ATaskResponse,
    status_code=201,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def create_task(
    data: A2ATaskCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2ATaskResponse:
    """创建 A2A Task。"""
    row = await a2a_service.create_task(db, data, org_id=org_id)
    return A2ATaskResponse.model_validate(row)


@router.get(
    "/tasks",
    response_model=A2ATaskListResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def list_tasks(
    agent_card_id: uuid.UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2ATaskListResponse:
    """查询 A2A Task 列表。"""
    rows, total = await a2a_service.list_tasks(
        db, agent_card_id=agent_card_id, limit=limit, offset=offset, org_id=org_id
    )
    return A2ATaskListResponse(
        data=[A2ATaskResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=A2ATaskResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2ATaskResponse:
    """获取 A2A Task。"""
    row = await a2a_service.get_task(db, task_id, org_id=org_id)
    return A2ATaskResponse.model_validate(row)


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=A2ATaskResponse,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def cancel_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> A2ATaskResponse:
    """取消 A2A Task。"""
    try:
        row = await a2a_service.cancel_task(db, task_id, org_id=org_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return A2ATaskResponse.model_validate(row)
