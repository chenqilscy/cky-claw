"""认证业务逻辑层。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password, verify_password
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.models.user import User
from app.schemas.auth import UserRegister


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    """注册新用户。用户名或邮箱冲突返回 409。"""
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"用户名 '{data.username}' 或邮箱 '{data.email}' 已被注册")
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> str:
    """验证用户凭据，返回 access_token。失败抛出 NotFoundError。"""
    stmt = select(User).where(User.username == username, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("用户名或密码错误")
    return create_access_token(
        data={"sub": str(user.id), "role": user.role},
    )


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """按 ID 获取用户。"""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("用户不存在")
    stmt = select(User).where(User.id == uid, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("用户不存在")
    return user
