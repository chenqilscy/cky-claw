"""多环境管理 API 路由。"""

from __future__ import annotations
import uuid

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import get_current_user, get_org_id, require_permission
from app.schemas.environment import (
    BindingResponse,
    EnvironmentAgentsResponse,
    EnvironmentCreate,
    EnvironmentDiffResponse,
    EnvironmentListResponse,
    EnvironmentResponse,
    EnvironmentUpdate,
    PublishRequest,
    RollbackRequest,
)
from app.services import environment as environment_service

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


@router.get("", response_model=EnvironmentListResponse, dependencies=[Depends(require_permission("environments", "read"))])
async def list_environments(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentListResponse:
    """获取环境列表。"""
    rows = await environment_service.list_environments(db, org_id)
    return EnvironmentListResponse(data=[EnvironmentResponse.model_validate(r) for r in rows], total=len(rows))


@router.post("", response_model=EnvironmentResponse, status_code=201, dependencies=[Depends(require_permission("environments", "write"))])
async def create_environment(
    body: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentResponse:
    """创建环境。"""
    row = await environment_service.create_environment(db, body, org_id)
    return EnvironmentResponse.model_validate(row)


@router.get(
    "/diff",
    response_model=EnvironmentDiffResponse,
    dependencies=[Depends(require_permission("environments", "read"))],
)
async def diff_environments(
    agent: str = Query(..., description="Agent 名称"),
    env1: str = Query(...),
    env2: str = Query(...),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentDiffResponse:
    """对比两个环境中同一 Agent 的发布版本快照。"""
    snap1, snap2 = await environment_service.diff_environments(db, agent, env1, env2, org_id)
    return EnvironmentDiffResponse(
        agent_name=agent,
        env1=env1,
        env2=env2,
        snapshot_env1=snap1,
        snapshot_env2=snap2,
    )


@router.get("/{env_name}", response_model=EnvironmentResponse, dependencies=[Depends(require_permission("environments", "read"))])
async def get_environment(
    env_name: str,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentResponse:
    """获取环境详情。"""
    row = await environment_service.get_environment_by_name(db, env_name, org_id)
    return EnvironmentResponse.model_validate(row)


@router.put("/{env_name}", response_model=EnvironmentResponse, dependencies=[Depends(require_permission("environments", "write"))])
async def update_environment(
    env_name: str,
    body: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentResponse:
    """更新环境。"""
    row = await environment_service.update_environment(db, env_name, body, org_id)
    return EnvironmentResponse.model_validate(row)


@router.delete("/{env_name}", dependencies=[Depends(require_permission("environments", "write"))])
async def delete_environment(
    env_name: str,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> dict[str, str]:
    """删除环境。"""
    await environment_service.delete_environment(db, env_name, org_id)
    return {"message": "环境已删除"}


@router.post(
    "/{env_name}/agents/{agent_name}/publish",
    response_model=BindingResponse,
    dependencies=[Depends(require_permission("environments", "write"))],
)
async def publish_agent(
    env_name: str,
    agent_name: str,
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> BindingResponse:
    """发布 Agent 到目标环境。"""
    row = await environment_service.publish_agent(
        db,
        env_name,
        agent_name,
        body.version_id,
        body.notes,
        org_id,
        user.id,
    )
    return BindingResponse.model_validate(row)


@router.post(
    "/{env_name}/agents/{agent_name}/rollback",
    response_model=BindingResponse,
    dependencies=[Depends(require_permission("environments", "write"))],
)
async def rollback_agent(
    env_name: str,
    agent_name: str,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> BindingResponse:
    """回滚目标环境中的 Agent。"""
    row = await environment_service.rollback_agent(
        db,
        env_name,
        agent_name,
        body.target_version_id,
        body.notes,
        org_id,
        user.id,
    )
    return BindingResponse.model_validate(row)


@router.get(
    "/{env_name}/agents",
    response_model=EnvironmentAgentsResponse,
    dependencies=[Depends(require_permission("environments", "read"))],
)
async def list_environment_agents(
    env_name: str,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> EnvironmentAgentsResponse:
    """获取环境内已发布 Agent 列表。"""
    rows = await environment_service.list_environment_agents(db, env_name, org_id)
    return EnvironmentAgentsResponse(
        environment=env_name,
        data=[BindingResponse.model_validate(r) for r in rows],
    )


