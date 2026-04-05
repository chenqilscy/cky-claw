"""OAuth 业务逻辑层。

支持 GitHub / 企微 / 钉钉 / 飞书 四种 OAuth Provider。
每种 Provider 通过分发表（dispatch dict）挂载独立的 token 交换、
用户信息获取和授权 URL 构建函数。
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

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

    # Provider 分发：自定义或默认 URL 构建
    builder = _CUSTOM_AUTHORIZE_BUILDERS.get(provider)
    if builder is not None:
        authorize_url = builder(config, state)
    else:
        params = urlencode({
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": config.scope,
            "state": state,
        })
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
    # 1. 验证 state（原子消费，防止并发重放）
    redis = await get_redis()
    redis_key = f"{_STATE_PREFIX}{state}"
    stored_provider = await redis.getdel(redis_key)
    if stored_provider is None or stored_provider != provider:
        raise ValidationError("OAuth state 验证失败，请重新授权")

    # 2. 获取 Provider 配置
    config = get_provider_config(provider)
    if config is None:
        raise ValidationError(f"OAuth Provider '{provider}' 不存在或未配置")

    # 3. 用 code 换取 access_token
    access_token = await _exchange_code_for_token(config, code)

    # 4. 获取用户信息（企微等 Provider 需要 code 参数）
    user_info = await _fetch_user_info(config, access_token, code=code)

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
    # 验证 state（原子消费）
    redis = await get_redis()
    redis_key = f"{_STATE_PREFIX}{state}"
    stored_provider = await redis.getdel(redis_key)
    if stored_provider is None or stored_provider != provider:
        raise ValidationError("OAuth state 验证失败，请重新授权")

    config = get_provider_config(provider)
    if config is None:
        raise ValidationError(f"OAuth Provider '{provider}' 不存在或未配置")

    access_token = await _exchange_code_for_token(config, code)
    user_info = await _fetch_user_info(config, access_token, code=code)

    raw_id = user_info.get("id")
    if raw_id is None:
        raise AuthenticationError("OAuth Provider 未返回用户 ID")
    provider_user_id = str(raw_id)

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


# ------ Provider 分发表 ------

# 授权 URL 构建器：provider_name → (config, state) -> url
_CUSTOM_AUTHORIZE_BUILDERS: dict[str, Callable[[OAuthProviderConfig, str], str]] = {}

# Token 交换器：provider_name → async (config, code) -> access_token
_CUSTOM_TOKEN_EXCHANGERS: dict[
    str, Callable[[OAuthProviderConfig, str], Awaitable[str]]
] = {}

# 用户信息获取器：provider_name → async (config, access_token, code) -> user_info
_CUSTOM_USERINFO_FETCHERS: dict[
    str, Callable[[OAuthProviderConfig, str, str], Awaitable[dict[str, Any]]]
] = {}


# ------ 企微 (WeCom) ------


def _build_authorize_url_wecom(config: OAuthProviderConfig, state: str) -> str:
    """构建企微 SSO 授权 URL。"""
    params = urlencode({
        "login_type": "CorpApp",
        "appid": config.client_id,
        "agentid": settings.oauth_wecom_agent_id,
        "redirect_uri": config.redirect_uri,
        "state": state,
    })
    return f"{config.authorize_url}?{params}"


async def _exchange_code_for_token_wecom(
    config: OAuthProviderConfig, code: str
) -> str:
    """企微：获取企业 access_token（corp-level，非用户级）。

    TODO: 企微 corp access_token 有效期 2 小时，后续可加 Redis 缓存避免重复请求。
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.token_url,
                params={
                    "corpid": config.client_id,
                    "corpsecret": config.client_secret,
                },
            )
    except httpx.HTTPError as exc:
        logger.error("企微 access_token 获取网络异常: %s", exc)
        raise AuthenticationError("OAuth 服务暂不可用，请稍后重试") from exc

    if resp.status_code != 200:
        raise AuthenticationError("企微 access_token 获取失败")

    data = resp.json()
    if data.get("errcode", 0) != 0:
        raise AuthenticationError(
            f"企微 access_token 获取失败: {data.get('errmsg', '未知错误')}"
        )

    token = data.get("access_token")
    if not token:
        raise AuthenticationError("企微响应中缺少 access_token")
    return str(token)


async def _fetch_user_info_wecom(
    config: OAuthProviderConfig, access_token: str, code: str
) -> dict[str, Any]:
    """企微：先用 code 获取 userid，再获取用户详情。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: code → userid
            resp = await client.get(
                config.userinfo_url,
                params={"access_token": access_token, "code": code},
            )
            if resp.status_code != 200:
                raise AuthenticationError("获取企微用户身份失败")

            identity = resp.json()
            if identity.get("errcode", 0) != 0:
                raise AuthenticationError(
                    f"获取企微用户身份失败: {identity.get('errmsg', '未知错误')}"
                )

            userid = identity.get("userid") or identity.get("UserId")
            if not userid:
                raise AuthenticationError("企微未返回用户 ID")

            # Step 2: userid → 用户详情
            resp2 = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/user/get",
                params={"access_token": access_token, "userid": userid},
            )
            if resp2.status_code != 200 or resp2.json().get("errcode", 0) != 0:
                # 降级：仅返回基础身份
                return {"id": userid, "name": userid}

            detail = resp2.json()
            return {
                "id": userid,
                "name": detail.get("name", userid),
                "email": detail.get("email", ""),
                "avatar_url": detail.get("avatar", ""),
            }
    except httpx.HTTPError as exc:
        logger.error("获取企微用户信息网络异常: %s", exc)
        raise AuthenticationError("获取企微用户信息失败，请稍后重试") from exc


# ------ 钉钉 (DingTalk) ------


def _build_authorize_url_dingtalk(config: OAuthProviderConfig, state: str) -> str:
    """构建钉钉授权 URL。"""
    params = urlencode({
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
        "response_type": "code",
        "state": state,
        "prompt": "consent",
    })
    return f"{config.authorize_url}?{params}"


async def _exchange_code_for_token_dingtalk(
    config: OAuthProviderConfig, code: str
) -> str:
    """钉钉：JSON body 格式换取 userAccessToken。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                config.token_url,
                json={
                    "clientId": config.client_id,
                    "clientSecret": config.client_secret,
                    "code": code,
                    "grantType": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:
        logger.error("钉钉 token 交换网络异常: %s", exc)
        raise AuthenticationError("OAuth 服务暂不可用，请稍后重试") from exc

    if resp.status_code != 200:
        raise AuthenticationError("钉钉 accessToken 获取失败")

    data = resp.json()
    token = data.get("accessToken")
    if not token:
        raise AuthenticationError(
            f"钉钉 accessToken 获取失败: {data.get('message', '未知错误')}"
        )
    return str(token)


async def _fetch_user_info_dingtalk(
    config: OAuthProviderConfig, access_token: str, code: str
) -> dict[str, Any]:
    """钉钉：通过 x-acs-dingtalk-access-token 获取用户信息。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.userinfo_url,
                headers={"x-acs-dingtalk-access-token": access_token},
            )
    except httpx.HTTPError as exc:
        logger.error("获取钉钉用户信息网络异常: %s", exc)
        raise AuthenticationError("获取钉钉用户信息失败，请稍后重试") from exc

    if resp.status_code != 200:
        raise AuthenticationError("获取钉钉用户信息失败")

    data = resp.json()
    return {
        "id": data.get("openId", data.get("unionId", "")),
        "name": data.get("nick", ""),
        "email": data.get("email", ""),
        "avatar_url": data.get("avatarUrl", ""),
    }


# ------ 飞书 (Feishu) ------


def _build_authorize_url_feishu(config: OAuthProviderConfig, state: str) -> str:
    """构建飞书授权 URL。"""
    params = urlencode({
        "app_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "state": state,
    })
    return f"{config.authorize_url}?{params}"


async def _exchange_code_for_token_feishu(
    config: OAuthProviderConfig, code: str
) -> str:
    """飞书：先获取 app_access_token，再用 code 换取 user_access_token。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: 获取 app_access_token
            app_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
                json={
                    "app_id": config.client_id,
                    "app_secret": config.client_secret,
                },
            )
            if app_resp.status_code != 200:
                raise AuthenticationError("飞书 app_access_token 获取失败")

            app_data = app_resp.json()
            app_token = app_data.get("app_access_token")
            if not app_token:
                raise AuthenticationError(
                    f"飞书 app_access_token 获取失败: {app_data.get('msg', '未知错误')}"
                )

            # Step 2: code → user_access_token
            resp = await client.post(
                config.token_url,
                json={"grant_type": "authorization_code", "code": code},
                headers={"Authorization": f"Bearer {app_token}"},
            )
    except httpx.HTTPError as exc:
        logger.error("飞书 token 交换网络异常: %s", exc)
        raise AuthenticationError("OAuth 服务暂不可用，请稍后重试") from exc

    if resp.status_code != 200:
        raise AuthenticationError("飞书 user_access_token 获取失败")

    data = resp.json()
    token_data = data.get("data", data)
    token = token_data.get("access_token")
    if not token:
        msg = data.get("msg", data.get("message", "未知错误"))
        raise AuthenticationError(f"飞书 user_access_token 获取失败: {msg}")
    return str(token)


async def _fetch_user_info_feishu(
    config: OAuthProviderConfig, access_token: str, code: str
) -> dict[str, Any]:
    """飞书：标准 Bearer token 获取用户信息。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.error("获取飞书用户信息网络异常: %s", exc)
        raise AuthenticationError("获取飞书用户信息失败，请稍后重试") from exc

    if resp.status_code != 200:
        raise AuthenticationError("获取飞书用户信息失败")

    raw = resp.json()
    data = raw.get("data", raw)
    avatar = data.get("avatar_url", "")
    if not avatar and isinstance(data.get("avatar"), dict):
        avatar = data["avatar"].get("avatar_origin", "")
    return {
        "id": data.get("open_id", data.get("user_id", "")),
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "avatar_url": avatar,
    }


# ------ OIDC (Keycloak / Casdoor / 通用) ------


def _build_authorize_url_oidc(config: OAuthProviderConfig, state: str) -> str:
    """构建标准 OIDC 授权 URL。

    OIDC 授权端点需要 response_type=code 参数（默认 OAuth 构建缺少此参数）。
    """
    params = urlencode({
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
        "state": state,
        "response_type": "code",
    })
    return f"{config.authorize_url}?{params}"


async def _fetch_user_info_oidc(
    config: OAuthProviderConfig, access_token: str, code: str
) -> dict[str, Any]:
    """OIDC 标准 UserInfo 端点 → 映射为内部用户信息格式。

    OIDC 标准字段映射：
    - sub → id
    - preferred_username → login
    - name → name
    - email → email
    - picture → avatar_url
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        logger.error("获取 OIDC 用户信息网络异常: %s", exc)
        raise AuthenticationError("获取 OIDC 用户信息失败，请稍后重试") from exc

    if resp.status_code != 200:
        logger.error("获取 OIDC 用户信息失败: status=%d", resp.status_code)
        raise AuthenticationError("获取 OIDC 用户信息失败")

    data = resp.json()
    return {
        "id": data.get("sub", ""),
        "login": data.get("preferred_username", data.get("name", "")),
        "name": data.get("name", data.get("preferred_username", "")),
        "email": data.get("email", ""),
        "avatar_url": data.get("picture", ""),
    }


# ------ Google ------


def _build_authorize_url_google(config: OAuthProviderConfig, state: str) -> str:
    """构建 Google OAuth 授权 URL。

    Google 需要 response_type=code 和 access_type=offline。
    """
    params = urlencode({
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
        "state": state,
        "response_type": "code",
        "access_type": "offline",
    })
    return f"{config.authorize_url}?{params}"


async def _fetch_user_info_google(
    config: OAuthProviderConfig, access_token: str, code: str
) -> dict[str, Any]:
    """Google UserInfo 端点 → 映射为内部用户信息格式。

    Google 返回字段：id, name, email, picture 等。
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.error("获取 Google 用户信息网络异常: %s", exc)
        raise AuthenticationError("获取 Google 用户信息失败，请稍后重试") from exc

    if resp.status_code != 200:
        logger.error("获取 Google 用户信息失败: status=%d", resp.status_code)
        raise AuthenticationError("获取 Google 用户信息失败")

    data = resp.json()
    return {
        "id": data.get("id", ""),
        "login": data.get("email", data.get("name", "")),
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "avatar_url": data.get("picture", ""),
    }


# ------ 注册分发表 ------

_CUSTOM_AUTHORIZE_BUILDERS.update({
    "wecom": _build_authorize_url_wecom,
    "dingtalk": _build_authorize_url_dingtalk,
    "feishu": _build_authorize_url_feishu,
    "oidc": _build_authorize_url_oidc,
    "google": _build_authorize_url_google,
})

_CUSTOM_TOKEN_EXCHANGERS.update({
    "wecom": _exchange_code_for_token_wecom,
    "dingtalk": _exchange_code_for_token_dingtalk,
    "feishu": _exchange_code_for_token_feishu,
    # OIDC / Google 使用默认标准 OAuth 2.0 form-encoded 流程，无需自定义
})

_CUSTOM_USERINFO_FETCHERS.update({
    "wecom": _fetch_user_info_wecom,
    "dingtalk": _fetch_user_info_dingtalk,
    "feishu": _fetch_user_info_feishu,
    "oidc": _fetch_user_info_oidc,
    "google": _fetch_user_info_google,
})


# ------ 默认（GitHub 等标准 OAuth 2.0）内部函数 ------


async def _exchange_code_for_token(config: OAuthProviderConfig, code: str) -> str:
    """用 authorization code 换取 access_token。

    优先使用 provider 级自定义实现，否则走标准 OAuth 2.0 form-encoded 流程。
    """
    custom = _CUSTOM_TOKEN_EXCHANGERS.get(config.name)
    if custom is not None:
        return await custom(config, code)

    # 默认：标准 OAuth 2.0（GitHub 等）
    try:
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
    except httpx.HTTPError as exc:
        logger.error("OAuth token 交换网络异常: %s", exc)
        raise AuthenticationError("OAuth 服务暂不可用，请稍后重试") from exc

    if resp.status_code != 200:
        logger.error("OAuth token 交换失败: status=%d body=%s", resp.status_code, resp.text)
        raise AuthenticationError("OAuth 授权码验证失败")

    data = resp.json()
    token = data.get("access_token")
    if not token:
        error = data.get("error_description", data.get("error", "未知错误"))
        raise AuthenticationError(f"OAuth token 获取失败: {error}")
    return str(token)


async def _fetch_user_info(
    config: OAuthProviderConfig, access_token: str, *, code: str = ""
) -> dict[str, Any]:
    """用 access_token 获取用户信息。

    优先使用 provider 级自定义实现，否则走标准 Bearer token GET 流程。
    code 参数传递给需要它的 Provider（如企微）。
    """
    custom = _CUSTOM_USERINFO_FETCHERS.get(config.name)
    if custom is not None:
        return await custom(config, access_token, code)

    # 默认：标准 Bearer token（GitHub 等）
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                config.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        logger.error("获取 OAuth 用户信息网络异常: %s", exc)
        raise AuthenticationError("获取 OAuth 用户信息失败，请稍后重试") from exc

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
    raw_id = user_info.get("id")
    if raw_id is None:
        raise AuthenticationError("OAuth Provider 未返回用户 ID")
    provider_user_id = str(raw_id)

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

    # 2. 查邮箱匹配（仅当 Provider 返回了邮箱时）
    # 安全提醒：邮箱自动绑定依赖 Provider 的邮箱验证策略。
    # GitHub /user API 仅返回已验证的公开邮箱，风险可控。
    # 新增 Provider 时需评估其邮箱可信度。
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
    # 确保唯一性（最多重试 100 次）
    base_username = username
    counter = 0
    max_attempts = 100
    while True:
        check = (await db.execute(
            select(User).where(User.username == username)
        )).scalar_one_or_none()
        if check is None:
            break
        counter += 1
        if counter >= max_attempts:
            raise ConflictError(f"无法生成唯一用户名（尝试了 {max_attempts} 次）")
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
