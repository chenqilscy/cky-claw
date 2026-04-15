"""角色管理 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.role import (
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)
from app.services import role as role_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@router.get("", response_model=RoleListResponse)
async def list_roles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> RoleListResponse:
    """列出所有角色。"""
    roles, total = await role_service.list_roles(db, limit=limit, offset=offset)
    return RoleListResponse(
        data=[RoleResponse.model_validate(r) for r in roles],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> RoleResponse:
    """创建新角色。"""
    role = await role_service.create_role(db, data)
    return RoleResponse.model_validate(role)


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> RoleResponse:
    """获取角色详情。"""
    role = await role_service.get_role(db, role_id)
    return RoleResponse.model_validate(role)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> RoleResponse:
    """更新角色。"""
    role = await role_service.update_role(db, role_id, data)
    return RoleResponse.model_validate(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> None:
    """删除角色。"""
    await role_service.delete_role(db, role_id)


@router.post("/{role_id}/assign/{user_id}", response_model=dict)
async def assign_role(
    role_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> dict[str, Any]:
    """为用户分配角色。"""
    user = await role_service.assign_role_to_user(db, user_id, role_id)
    return {"message": f"已将角色分配给用户 {user.username}"}
