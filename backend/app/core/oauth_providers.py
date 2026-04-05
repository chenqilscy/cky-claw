"""OAuth Provider 配置 — 提供可扩展的 OAuth Provider 注册机制。"""

from __future__ import annotations

from dataclasses import dataclass


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


# Provider 注册表：名称 → 配置获取函数
_PROVIDER_FACTORIES: dict[str, object] = {
    "github": get_github_provider,
}


def get_provider_config(provider: str) -> OAuthProviderConfig | None:
    """按名称获取 Provider 配置。不存在或未配置时返回 None。"""
    factory = _PROVIDER_FACTORIES.get(provider)
    if factory is None:
        return None
    return factory()  # type: ignore[operator]


def list_available_providers() -> list[str]:
    """列出所有已配置（client_id 非空）的 Provider 名称。"""
    result: list[str] = []
    for name, factory in _PROVIDER_FACTORIES.items():
        config = factory()  # type: ignore[operator]
        if config is not None:
            result.append(name)
    return result
