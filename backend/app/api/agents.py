"""Agent 管理 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import AgentCreate, AgentListResponse, AgentResponse, AgentUpdate
from app.services import agent as agent_service

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    search: str | None = Query(None, description="按名称/描述模糊搜索"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> AgentListResponse:
    """获取 Agent 列表。"""
    agents, total = await agent_service.list_agents(db, search=search, limit=limit, offset=offset)
    return AgentListResponse(
        data=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """创建 Agent。"""
    agent = await agent_service.create_agent(db, data)
    return AgentResponse.model_validate(agent)


@router.get("/{name}", response_model=AgentResponse)
async def get_agent(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """获取 Agent 详情。"""
    agent = await agent_service.get_agent_by_name(db, name)
    return AgentResponse.model_validate(agent)


@router.put("/{name}", response_model=AgentResponse)
async def update_agent(
    name: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """更新 Agent（PATCH 语义）。"""
    agent = await agent_service.update_agent(db, name, data)
    return AgentResponse.model_validate(agent)


@router.delete("/{name}")
async def delete_agent(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除 Agent（软删除）。"""
    await agent_service.delete_agent(db, name)
    return {"message": "Agent deleted"}
