"""认证业务逻辑层。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_password_reset_token,
    hash_password,
    is_token_blacklisted,
    store_password_reset_token,
    validate_password_reset_token,
    verify_password,
)
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
        raise ConflictError(f"用户名 '{data.username}' 或邮箱 '{data.email}' 已被注册") from None
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> tuple[str, str]:
    """验证用户凭据，返回 (access_token, refresh_token)。失败抛出 AuthenticationError。"""
    stmt = select(User).where(User.username == username, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("用户名或密码错误")
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return access_token, refresh_token


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """用 refresh_token 签发新的 access_token + refresh_token。"""
    # 检查黑名单
    if await is_token_blacklisted(refresh_token):
        raise AuthenticationError("Refresh Token 已失效")

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        raise AuthenticationError("Refresh Token 无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Refresh Token 无效")

    # 验证用户仍然有效
    user = await get_user_by_id(db, user_id)

    # 旧 refresh_token 加入黑名单（令牌轮转）
    exp = payload.get("exp", 0)
    import time
    remaining = max(int(exp - time.time()), 1)
    await blacklist_token(refresh_token, remaining)

    # 签发新 token 对
    token_data = {"sub": str(user.id), "role": user.role}
    new_access = create_access_token(data=token_data)
    new_refresh = create_refresh_token(data=token_data)
    return new_access, new_refresh


async def logout_user(access_token: str, refresh_token: str | None = None) -> None:
    """服务端登出——将 token 加入黑名单。"""
    # access_token 黑名单
    payload = decode_access_token(access_token)
    if payload:
        exp = payload.get("exp", 0)
        import time
        remaining = max(int(exp - time.time()), 1)
        await blacklist_token(access_token, remaining)

    # refresh_token 黑名单（如提供）
    if refresh_token:
        r_payload = decode_access_token(refresh_token)
        if r_payload:
            exp = r_payload.get("exp", 0)
            import time
            remaining = max(int(exp - time.time()), 1)
            await blacklist_token(refresh_token, remaining)


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    """修改密码。需验证当前密码。"""
    if not verify_password(current_password, user.hashed_password):
        raise AuthenticationError("当前密码错误")
    if current_password == new_password:
        raise ValidationError("新密码不能与当前密码相同")
    user.hashed_password = hash_password(new_password)
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> str:
    """请求密码重置——生成 reset token 存 Redis。返回 token（实际生产应发邮件，此处直接返回）。"""
    stmt = select(User).where(User.email == email.lower(), User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        # 安全考虑：即使邮箱不存在也不报错，防止邮箱枚举
        return ""
    token = generate_password_reset_token()
    await store_password_reset_token(email.lower(), token)
    return token


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    """确认密码重置——验证 token 并设置新密码。"""
    email = await validate_password_reset_token(token)
    if email is None:
        raise AuthenticationError("重置令牌无效或已过期")
    stmt = select(User).where(User.email == email, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("用户不存在")
    user.hashed_password = hash_password(new_password)
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """按 ID 获取用户。"""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("用户不存在") from None
    stmt = select(User).where(User.id == uid, User.is_active == True)  # noqa: E712
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("用户不存在")
    return user
