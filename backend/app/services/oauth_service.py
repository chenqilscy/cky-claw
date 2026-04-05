"""OAuth 业务逻辑层。"""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.crypto import encrypt_api_key
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.oauth_providers import OAuthProviderConfig, get_provider_config
from app.core.redis import get_redis
from app.models.user import User
from app.models.user_oauth import UserOAuthConnection

logger = logging.getLogger(__name__)

# Redis key 前缀和过期时间
_STATE_PREFIX = "oauth:state:"
_STATE_TTL_SECONDS = 300  # 5 分钟


async def generate_authorize_url(provider: str) -> tuple[str, str]:
    """生成 OAuth 授权跳转 URL。

    返回 (authorize_url, state)。
    state 参数存入 Redis 用于 CSRF 防护。

    Raises:
        ValidationError: Provider 不存在或未配置。
    """
    config = get_provider_config(provider)
    if config is None:
        raise ValidationError(f"OAuth Provider '{provider}' 不存在或未配置")

    state = secrets.token_urlsafe(32)

    # 存入 Redis，5 分钟后过期
    redis = await get_redis()
    await redis.set(f"{_STATE_PREFIX}{state}", provider, ex=_STATE_TTL_SECONDS)

    params = (
        f"client_id={config.client_id}"
        f"&redirect_uri={config.redirect_uri}"
        f"&scope={config.scope}"
        f"&state={state}"
    )
    authorize_url = f"{config.authorize_url}?{params}"
    return authorize_url, state


async def handle_oauth_callback(
    db: AsyncSession,
    provider: str,
    code: str,
    state: str,
) -> str:
    """处理 OAuth 回调，返回 JWT access_token。

    流程：
    1. 验证 state（Redis 一次性消费）
    2. 用 code 向 Provider 换取 access_token
    3. 用 access_token 获取用户信息
    4. 创建或关联本地用户
    5. 返回 JWT

    Raises:
        ValidationError: state 验证失败或 Provider 未配置。
        AuthenticationError: OAuth token 交换或用户信息获取失败。
    """
    # 1. 验证 state
    redis = await get_redis()
    redis_key = f"{_STATE_PREFIX}{state}"
    stored_provider = await redis.get(redis_key)
    if stored_provider is None or stored_provider != provider:
        raise ValidationError("OAuth state 验证失败，请重新授权")
    # 一次性消费
    await redis.delete(redis_key)

    # 2. 获取 Provider 配置
    config = get_provider_config(provider)
    if config is None:
        raise ValidationError(f"OAuth Provider '{provider}' 不存在或未配置")

    # 3. 用 code 换取 access_token
    access_token = await _exchange_code_for_token(config, code)

    # 4. 获取用户信息
    user_info = await _fetch_user_info(config, access_token)

    # 5. 创建或关联用户
    user = await _find_or_create_user(db, config.name, user_info, access_token)

    # 6. 返回 JWT
    return create_access_token(
        data={"sub": str(user.id), "role": user.role},
    )


async def bind_oauth_to_user(
    db: AsyncSession,
    user: User,
    provider: str,
    code: str,
    state: str,
) -> UserOAuthConnection:
    """将 OAuth 绑定到已登录用户。

    Raises:
        ConflictError: 该 Provider 账号已被其他用户绑定。
    """
    # 验证 state
    redis = await get_redis()
    redis_key = f"{_STATE_PREFIX}{state}"
    stored_provider = await redis.get(redis_key)
    if stored_provider is None or stored_provider != provider:
        raise ValidationError("OAuth state 验证失败，请重新授权")
    await redis.delete(redis_key)

    config = get_provider_config(provider)
    if config is None:
        raise ValidationError(f"OAuth Provider '{provider}' 不存在或未配置")

    access_token = await _exchange_code_for_token(config, code)
    user_info = await _fetch_user_info(config, access_token)

    provider_user_id = str(user_info["id"])

    # 检查是否已绑定到其他用户
    stmt = select(UserOAuthConnection).where(
        UserOAuthConnection.provider == provider,
        UserOAuthConnection.provider_user_id == provider_user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        if existing.user_id != user.id:
            raise ConflictError(f"该 {provider} 账号已被其他用户绑定")
        return existing

    conn = UserOAuthConnection(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=user_info.get("login", user_info.get("name", "")),
        provider_email=user_info.get("email"),
        provider_avatar_url=user_info.get("avatar_url"),
        access_token_encrypted=encrypt_api_key(access_token),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def get_user_connections(
    db: AsyncSession, user_id: Any
) -> list[UserOAuthConnection]:
    """获取用户的所有 OAuth 绑定。"""
    stmt = select(UserOAuthConnection).where(
        UserOAuthConnection.user_id == user_id
    ).order_by(UserOAuthConnection.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def unbind_oauth(db: AsyncSession, user: User, provider: str) -> None:
    """解绑用户的 OAuth 绑定。

    Raises:
        NotFoundError: 未找到该 Provider 的绑定。
    """
    stmt = select(UserOAuthConnection).where(
        UserOAuthConnection.user_id == user.id,
        UserOAuthConnection.provider == provider,
    )
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if conn is None:
        raise NotFoundError(f"未找到 {provider} 的 OAuth 绑定")
    await db.delete(conn)
    await db.commit()


# ------ 内部函数 ------


async def _exchange_code_for_token(config: OAuthProviderConfig, code: str) -> str:
    """用 authorization code 换取 access_token。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            config.token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": config.redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            logger.error("OAuth token 交换失败: status=%d body=%s", resp.status_code, resp.text)
            raise AuthenticationError("OAuth 授权码验证失败")

        data = resp.json()
        token = data.get("access_token")
        if not token:
            error = data.get("error_description", data.get("error", "未知错误"))
            raise AuthenticationError(f"OAuth token 获取失败: {error}")
        return str(token)


async def _fetch_user_info(config: OAuthProviderConfig, access_token: str) -> dict[str, Any]:
    """用 access_token 获取用户信息。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            config.userinfo_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.error("获取 OAuth 用户信息失败: status=%d", resp.status_code)
            raise AuthenticationError("获取 OAuth 用户信息失败")
        return dict(resp.json())


async def _find_or_create_user(
    db: AsyncSession,
    provider: str,
    user_info: dict[str, Any],
    access_token: str,
) -> User:
    """基于 OAuth 用户信息查找或创建本地用户。

    先查 OAuth 绑定表，有则直接返回关联用户；
    再查邮箱匹配的本地用户并绑定；
    都没有则创建新用户。
    """
    provider_user_id = str(user_info["id"])

    # 1. 查已有绑定
    stmt = select(UserOAuthConnection).where(
        UserOAuthConnection.provider == provider,
        UserOAuthConnection.provider_user_id == provider_user_id,
    )
    existing_conn = (await db.execute(stmt)).scalar_one_or_none()
    if existing_conn is not None:
        # 更新 access_token
        existing_conn.access_token_encrypted = encrypt_api_key(access_token)
        existing_conn.provider_username = user_info.get("login", user_info.get("name", ""))
        existing_conn.provider_avatar_url = user_info.get("avatar_url")
        await db.commit()
        # 查关联用户
        user = (await db.execute(
            select(User).where(User.id == existing_conn.user_id, User.is_active == True)  # noqa: E712
        )).scalar_one_or_none()
        if user is None:
            raise AuthenticationError("关联用户已停用")
        return user

    # 2. 查邮箱匹配
    email = user_info.get("email")
    if email:
        user = (await db.execute(
            select(User).where(User.email == email.lower(), User.is_active == True)  # noqa: E712
        )).scalar_one_or_none()
        if user is not None:
            # 自动绑定
            conn = UserOAuthConnection(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_username=user_info.get("login", user_info.get("name", "")),
                provider_email=email,
                provider_avatar_url=user_info.get("avatar_url"),
                access_token_encrypted=encrypt_api_key(access_token),
            )
            db.add(conn)
            # 更新头像
            if user_info.get("avatar_url") and not user.avatar_url:
                user.avatar_url = user_info["avatar_url"]
            await db.commit()
            return user

    # 3. 创建新用户
    username = user_info.get("login", user_info.get("name", f"oauth_{provider}_{provider_user_id}"))
    # 确保唯一性
    base_username = username
    counter = 0
    while True:
        check = (await db.execute(
            select(User).where(User.username == username)
        )).scalar_one_or_none()
        if check is None:
            break
        counter += 1
        username = f"{base_username}_{counter}"

    new_user = User(
        username=username,
        email=email or f"{username}@oauth.{provider}",
        hashed_password="!oauth-no-password",  # OAuth 用户无密码登录
        avatar_url=user_info.get("avatar_url"),
    )
    db.add(new_user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"用户名 '{username}' 已被注册，请使用其他方式登录")

    # 绑定
    conn = UserOAuthConnection(
        user_id=new_user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=user_info.get("login", user_info.get("name", "")),
        provider_email=email,
        provider_avatar_url=user_info.get("avatar_url"),
        access_token_encrypted=encrypt_api_key(access_token),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(new_user)
    return new_user
