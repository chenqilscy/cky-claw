"""OAuth Provider 配置 — 提供可扩展的 OAuth Provider 注册机制。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OAuthProviderConfig:
    """OAuth Provider 配置项。"""

    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str
    scope: str
    redirect_uri: str


def get_github_provider() -> OAuthProviderConfig | None:
    """获取 GitHub OAuth Provider 配置。未配置时返回 None。"""
    from app.core.config import settings

    if not settings.oauth_github_client_id or not settings.oauth_github_client_secret:
        return None

    return OAuthProviderConfig(
        name="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        client_id=settings.oauth_github_client_id,
        client_secret=settings.oauth_github_client_secret,
        scope="read:user,user:email",
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/callback/github",
    )


def get_wecom_provider() -> OAuthProviderConfig | None:
    """获取企微 OAuth Provider 配置。未配置时返回 None。"""
    from app.core.config import settings

    if not settings.oauth_wecom_corp_id or not settings.oauth_wecom_secret:
        return None

    return OAuthProviderConfig(
        name="wecom",
        authorize_url="https://login.work.weixin.qq.com/wwlogin/sso/login",
        token_url="https://qyapi.weixin.qq.com/cgi-bin/gettoken",
        userinfo_url="https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo",
        client_id=settings.oauth_wecom_corp_id,
        client_secret=settings.oauth_wecom_secret,
        scope="",
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/callback/wecom",
    )


def get_dingtalk_provider() -> OAuthProviderConfig | None:
    """获取钉钉 OAuth Provider 配置。未配置时返回 None。"""
    from app.core.config import settings

    if not settings.oauth_dingtalk_client_id or not settings.oauth_dingtalk_client_secret:
        return None

    return OAuthProviderConfig(
        name="dingtalk",
        authorize_url="https://login.dingtalk.com/oauth2/auth",
        token_url="https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
        userinfo_url="https://api.dingtalk.com/v1.0/contact/users/me",
        client_id=settings.oauth_dingtalk_client_id,
        client_secret=settings.oauth_dingtalk_client_secret,
        scope="openid",
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/callback/dingtalk",
    )


def get_feishu_provider() -> OAuthProviderConfig | None:
    """获取飞书 OAuth Provider 配置。未配置时返回 None。"""
    from app.core.config import settings

    if not settings.oauth_feishu_app_id or not settings.oauth_feishu_app_secret:
        return None

    return OAuthProviderConfig(
        name="feishu",
        authorize_url="https://open.feishu.cn/open-apis/authen/v1/authorize",
        token_url="https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
        userinfo_url="https://open.feishu.cn/open-apis/authen/v1/user_info",
        client_id=settings.oauth_feishu_app_id,
        client_secret=settings.oauth_feishu_app_secret,
        scope="",
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/callback/feishu",
    )


# OIDC Discovery 缓存（模块级，进程生命周期有效）
_oidc_discovery_cache: dict[str, Any] | None = None


def _discover_oidc_endpoints(issuer: str) -> dict[str, Any] | None:
    """执行 OIDC Discovery，获取 well-known 配置并缓存。

    通过 {issuer}/.well-known/openid-configuration 自动发现端点。
    结果缓存在模块级变量中，重启服务刷新。
    """
    global _oidc_discovery_cache
    if _oidc_discovery_cache is not None:
        return _oidc_discovery_cache

    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        resp = httpx.get(discovery_url, timeout=10.0)
        if resp.status_code != 200:
            logger.error("OIDC Discovery 失败: status=%d url=%s", resp.status_code, discovery_url)
            return None

        data = resp.json()
        # 验证必需字段
        required = ("authorization_endpoint", "token_endpoint")
        for key in required:
            if key not in data:
                logger.error("OIDC Discovery 响应缺少必需字段: %s", key)
                return None

        _oidc_discovery_cache = data
        return data
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("OIDC Discovery 网络异常: %s", exc)
        return None


def get_oidc_provider() -> OAuthProviderConfig | None:
    """获取通用 OIDC Provider 配置（支持 Keycloak / Casdoor 等）。

    自动从 OIDC Issuer 的 .well-known/openid-configuration 发现端点。
    未配置或 Discovery 失败时返回 None。
    """
    from app.core.config import settings

    if not settings.oauth_oidc_issuer or not settings.oauth_oidc_client_id:
        return None

    discovery = _discover_oidc_endpoints(settings.oauth_oidc_issuer)
    if discovery is None:
        return None

    return OAuthProviderConfig(
        name="oidc",
        authorize_url=discovery["authorization_endpoint"],
        token_url=discovery["token_endpoint"],
        userinfo_url=discovery.get("userinfo_endpoint", f"{settings.oauth_oidc_issuer}/userinfo"),
        client_id=settings.oauth_oidc_client_id,
        client_secret=settings.oauth_oidc_client_secret,
        scope=settings.oauth_oidc_scope,
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/callback/oidc",
    )


# Provider 注册表：名称 → 配置获取函数
_PROVIDER_FACTORIES: dict[str, Callable[[], OAuthProviderConfig | None]] = {
    "github": get_github_provider,
    "wecom": get_wecom_provider,
    "dingtalk": get_dingtalk_provider,
    "feishu": get_feishu_provider,
    "oidc": get_oidc_provider,
}


def get_provider_config(provider: str) -> OAuthProviderConfig | None:
    """按名称获取 Provider 配置。不存在或未配置时返回 None。"""
    factory = _PROVIDER_FACTORIES.get(provider)
    if factory is None:
        return None
    return factory()


def list_available_providers() -> list[str]:
    """列出所有已配置（client_id 非空）的 Provider 名称。"""
    result: list[str] = []
    for name, factory in _PROVIDER_FACTORIES.items():
        config = factory()
        if config is not None:
            result.append(name)
    return result
