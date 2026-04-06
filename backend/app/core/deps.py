"""认证依赖注入。"""

from __future__ import annotations


import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.database import get_db as get_db  # noqa: PLC0414 — explicit re-export
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 获取当前用户。"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token 无效或已过期"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token 缺少用户标识"},
        )

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token 用户标识无效"},
        )

    stmt = select(User).where(User.id == uid, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "用户不存在或已停用"},
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求当前用户为 Admin。"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "需要管理员权限"},
        )
    return user


def require_permission(resource: str, action: str) -> Callable[..., object]:
    """工厂函数：生成权限检查依赖。

    若用户绑定了 Role 且 Role 含有 permissions JSONB，则检查 JSONB；
    否则回退到 user.role 字段（admin 具有全部权限，user 具有 read 权限）。
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # 优先检查 role_id 绑定的 Role permissions
        if user.role_id is not None:
            from app.models.role import Role

            stmt = select(Role).where(Role.id == user.role_id)
            role = (await db.execute(stmt)).scalar_one_or_none()
            if role is not None:
                actions = role.permissions.get(resource, [])
                if action in actions:
                    return user
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": f"角色 '{role.name}' 缺少 {resource}.{action} 权限",
                    },
                )

        # 回退：兼容旧 role 字段
        if user.role == "admin":
            return user
        if action == "read":
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": f"当前角色缺少 {resource}.{action} 权限",
            },
        )

    return _check


async def get_org_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID | None:
    """从当前用户提取 org_id，用于租户隔离过滤。

    返回 None 表示用户未绑定组织（或 admin 全局模式）。
    """
    return user.org_id
