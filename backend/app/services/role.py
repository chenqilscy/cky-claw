"""角色业务逻辑层。"""

from __future__ import annotations

from typing import Any

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleUpdate

# 系统预设角色定义
SYSTEM_ROLES = [
    {
        "name": "admin",
        "description": "管理员 — 拥有全部权限",
        "permissions": {
            "agents": ["read", "write", "delete", "execute"],
            "providers": ["read", "write", "delete"],
            "workflows": ["read", "write", "delete", "execute"],
            "teams": ["read", "write", "delete"],
            "guardrails": ["read", "write", "delete"],
            "mcp_servers": ["read", "write", "delete"],
            "tool_groups": ["read", "write", "delete"],
            "skills": ["read", "write", "delete"],
            "templates": ["read", "write", "delete"],
            "memories": ["read", "write", "delete"],
            "runs": ["read", "write", "delete"],
            "traces": ["read"],
            "approvals": ["read", "write"],
            "sessions": ["read", "write", "delete"],
            "token_usage": ["read"],
            "audit_logs": ["read"],
            "roles": ["read", "write", "delete"],
            "users": ["read", "write", "delete"],
        },
        "is_system": True,
    },
    {
        "name": "user",
        "description": "普通用户 — 基本读写权限",
        "permissions": {
            "agents": ["read", "write", "execute"],
            "providers": ["read"],
            "workflows": ["read", "write", "execute"],
            "teams": ["read"],
            "guardrails": ["read"],
            "mcp_servers": ["read"],
            "tool_groups": ["read"],
            "skills": ["read", "write"],
            "templates": ["read"],
            "memories": ["read", "write"],
            "runs": ["read"],
            "traces": ["read"],
            "approvals": ["read", "write"],
            "sessions": ["read", "write"],
            "token_usage": ["read"],
            "audit_logs": ["read"],
            "roles": ["read"],
            "users": ["read"],
        },
        "is_system": True,
    },
    {
        "name": "viewer",
        "description": "只读用户 — 仅读取权限",
        "permissions": {
            "agents": ["read"],
            "providers": ["read"],
            "workflows": ["read"],
            "teams": ["read"],
            "guardrails": ["read"],
            "mcp_servers": ["read"],
            "tool_groups": ["read"],
            "skills": ["read"],
            "templates": ["read"],
            "memories": ["read"],
            "runs": ["read"],
            "traces": ["read"],
            "approvals": ["read"],
            "sessions": ["read"],
            "token_usage": ["read"],
            "audit_logs": ["read"],
            "roles": ["read"],
            "users": ["read"],
        },
        "is_system": True,
    },
]


async def seed_system_roles(db: AsyncSession) -> None:
    """初始化系统预设角色（幂等操作）。"""
    for role_def in SYSTEM_ROLES:
        stmt = select(Role).where(Role.name == role_def["name"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            role = Role(**role_def)
            db.add(role)
    await db.commit()


async def create_role(db: AsyncSession, data: RoleCreate) -> Role:
    """创建角色。"""
    role = Role(
        name=data.name,
        description=data.description,
        permissions=data.permissions,
    )
    db.add(role)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"角色名 '{data.name}' 已存在")
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: uuid.UUID, data: RoleUpdate) -> Role:
    """更新角色。系统角色不允许修改权限。"""
    stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(stmt)).scalar_one_or_none()
    if role is None:
        raise NotFoundError("角色不存在")
    if role.is_system and data.permissions is not None:
        raise ValidationError("系统内置角色不允许修改权限")
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: uuid.UUID) -> None:
    """删除角色。系统角色不允许删除。"""
    stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(stmt)).scalar_one_or_none()
    if role is None:
        raise NotFoundError("角色不存在")
    if role.is_system:
        raise ValidationError("系统内置角色不允许删除")
    # 检查是否有用户引用该角色
    user_count_stmt = select(func.count()).select_from(User).where(User.role_id == role_id)
    count = (await db.execute(user_count_stmt)).scalar() or 0
    if count > 0:
        raise ValidationError(f"该角色下还有 {count} 个用户，无法删除")
    await db.delete(role)
    await db.commit()


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    """获取角色。"""
    stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(stmt)).scalar_one_or_none()
    if role is None:
        raise NotFoundError("角色不存在")
    return role


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    """按名称获取角色。"""
    stmt = select(Role).where(Role.name == name)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_roles(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> tuple[list[Role], int]:
    """列出角色。"""
    count_stmt = select(func.count()).select_from(Role)
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = select(Role).order_by(Role.created_at).limit(limit).offset(offset)
    roles = list((await db.execute(stmt)).scalars().all())
    return roles, total


async def assign_role_to_user(db: AsyncSession, user_id: uuid.UUID, role_id: uuid.UUID) -> User:
    """为用户分配角色。"""
    # 验证角色存在
    role_stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(role_stmt)).scalar_one_or_none()
    if role is None:
        raise NotFoundError("角色不存在")
    # 验证用户存在
    user_stmt = select(User).where(User.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("用户不存在")
    user.role_id = role_id
    user.role = role.name  # 同步更新兼容字段
    await db.commit()
    await db.refresh(user)
    return user


def check_permission(permissions: dict[str, Any], resource: str, action: str) -> bool:
    """检查权限字典中是否包含指定资源的指定操作。"""
    actions = permissions.get(resource, [])
    return action in actions
