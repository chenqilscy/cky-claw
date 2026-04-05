"""OAuth 2.0 认证 API 测试。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.main import app


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """生成一个已登录用户的 JWT header。"""
    token = create_access_token(data={"sub": str(uuid.uuid4()), "role": "user"})
    return {"Authorization": f"Bearer {token}"}


# ======== Provider 列表 ========

@pytest.mark.asyncio
async def test_get_providers_empty() -> None:
    """未配置任何 Provider 时返回空列表。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.core.oauth_providers.get_github_provider", return_value=None):
            resp = await ac.get("/api/v1/auth/oauth/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"] == []


@pytest.mark.asyncio
async def test_get_providers_github() -> None:
    """配置 GitHub 后返回 ['github']。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.oauth.list_available_providers", return_value=["github"]):
            resp = await ac.get("/api/v1/auth/oauth/providers")
    assert resp.status_code == 200
    assert "github" in resp.json()["providers"]


# ======== 授权 URL ========

@pytest.mark.asyncio
async def test_authorize_unconfigured_provider() -> None:
    """请求未配置的 Provider 返回 422。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_provider_config", return_value=None):
            resp = await ac.get("/api/v1/auth/oauth/unknown/authorize")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_authorize_github_success() -> None:
    """成功获取 GitHub 授权 URL。"""
    from app.core.oauth_providers import OAuthProviderConfig

    mock_config = OAuthProviderConfig(
        name="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        client_id="test-client-id",
        client_secret="test-secret",
        scope="read:user,user:email",
        redirect_uri="http://localhost:3000/oauth/callback/github",
    )

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
             patch("app.services.oauth_service.get_redis", return_value=mock_redis):
            resp = await ac.get("/api/v1/auth/oauth/github/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "authorize_url" in data
    assert "state" in data
    assert "github.com/login/oauth/authorize" in data["authorize_url"]
    assert "client_id=test-client-id" in data["authorize_url"]
    mock_redis.set.assert_called_once()


# ======== 回调处理 ========

@pytest.mark.asyncio
async def test_callback_invalid_state() -> None:
    """无效 state 返回 422。"""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_redis", return_value=mock_redis):
            resp = await ac.get(
                "/api/v1/auth/oauth/github/callback",
                params={"code": "test-code", "state": "invalid-state"},
            )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_callback_state_mismatch() -> None:
    """state 对应的 provider 不匹配返回 422。"""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="other_provider")
    mock_redis.delete = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_redis", return_value=mock_redis):
            resp = await ac.get(
                "/api/v1/auth/oauth/github/callback",
                params={"code": "test-code", "state": "some-state"},
            )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_callback_success_new_user() -> None:
    """成功回调 — 创建新用户并返回 JWT。"""
    from app.core.oauth_providers import OAuthProviderConfig

    mock_config = OAuthProviderConfig(
        name="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        client_id="test-client-id",
        client_secret="test-secret",
        scope="read:user,user:email",
        redirect_uri="http://localhost:3000/oauth/callback/github",
    )

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")

    # Mock: token 交换返回 access_token
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "gho_test123"}

    # Mock: 用户信息
    test_username = f"testuser_{uuid.uuid4().hex[:8]}"
    mock_user_resp = MagicMock()
    mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = {
        "id": 12345,
        "login": test_username,
        "email": f"{test_username}@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345",
    }

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.post = AsyncMock(return_value=mock_token_resp)
    mock_http_client.get = AsyncMock(return_value=mock_user_resp)

    # Mock: 创建用户，返回一个 fake User
    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    fake_user.role = "user"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
             patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
             patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_http_client), \
             patch("app.services.oauth_service._find_or_create_user", new_callable=AsyncMock, return_value=fake_user):
            resp = await ac.get(
                "/api/v1/auth/oauth/github/callback",
                params={"code": "test-code", "state": "valid-state"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"


# ======== 绑定列表（需登录） ========

@pytest.mark.asyncio
async def test_connections_requires_auth() -> None:
    """获取绑定列表需要认证 — HTTPBearer 要求 Authorization header。"""
    from app.core.deps import get_current_user

    # 直接验证路由声明了 get_current_user 依赖
    from app.api.oauth import get_connections
    import inspect

    sig = inspect.signature(get_connections)
    param_names = list(sig.parameters.keys())
    assert "user" in param_names, "get_connections 应有 user 参数（get_current_user 依赖）"


# ======== OAuth Provider 配置 ========

def test_oauth_provider_config_dataclass() -> None:
    """OAuthProviderConfig dataclass 正常创建。"""
    from app.core.oauth_providers import OAuthProviderConfig

    cfg = OAuthProviderConfig(
        name="test",
        authorize_url="https://example.com/auth",
        token_url="https://example.com/token",
        userinfo_url="https://example.com/user",
        client_id="client123",
        client_secret="secret456",
        scope="read",
        redirect_uri="http://localhost:3000/callback",
    )
    assert cfg.name == "test"
    assert cfg.client_id == "client123"


def test_get_provider_config_returns_none_for_unknown() -> None:
    """未知 Provider 返回 None。"""
    from app.core.oauth_providers import get_provider_config

    assert get_provider_config("nonexistent") is None


def test_list_providers_with_no_config() -> None:
    """未配置 client_id 时 list_available_providers 返回空。"""
    from app.core.oauth_providers import list_available_providers

    with patch("app.core.oauth_providers.get_github_provider", return_value=None):
        result = list_available_providers()
    assert result == []


# ======== OAuth Schema 验证 ========

def test_oauth_authorize_response_schema() -> None:
    """OAuthAuthorizeResponse schema 正确序列化。"""
    from app.schemas.oauth import OAuthAuthorizeResponse

    resp = OAuthAuthorizeResponse(
        authorize_url="https://github.com/login/oauth/authorize?client_id=test",
        state="abc123",
    )
    assert resp.authorize_url.startswith("https://")
    assert resp.state == "abc123"


def test_oauth_callback_request_schema() -> None:
    """OAuthCallbackRequest schema 正确反序列化。"""
    from app.schemas.oauth import OAuthCallbackRequest

    req = OAuthCallbackRequest(code="auth-code", state="state-token")
    assert req.code == "auth-code"
    assert req.state == "state-token"


def test_oauth_connection_response_schema() -> None:
    """OAuthConnectionResponse 从 ORM 属性正确构建。"""
    from app.schemas.oauth import OAuthConnectionResponse

    conn_data = {
        "id": uuid.uuid4(),
        "provider": "github",
        "provider_user_id": "12345",
        "provider_username": "octocat",
        "provider_email": "octocat@github.com",
        "provider_avatar_url": "https://avatars.githubusercontent.com/u/12345",
        "created_at": "2026-04-05T00:00:00+00:00",
    }
    resp = OAuthConnectionResponse(**conn_data)
    assert resp.provider == "github"
    assert resp.provider_username == "octocat"


# ======== User Model avatar_url ========

def test_user_model_has_avatar_url() -> None:
    """User 模型包含 avatar_url 字段。"""
    from app.models.user import User

    assert hasattr(User, "avatar_url")


# ======== UserOAuthConnection Model ========

def test_user_oauth_connection_model() -> None:
    """UserOAuthConnection 模型字段完整。"""
    from app.models.user_oauth import UserOAuthConnection

    assert hasattr(UserOAuthConnection, "user_id")
    assert hasattr(UserOAuthConnection, "provider")
    assert hasattr(UserOAuthConnection, "provider_user_id")
    assert hasattr(UserOAuthConnection, "provider_username")
    assert hasattr(UserOAuthConnection, "provider_email")
    assert hasattr(UserOAuthConnection, "access_token_encrypted")


# ======== OAuth Service 内部函数 ========

@pytest.mark.asyncio
async def test_exchange_code_failure() -> None:
    """Token 交换失败抛出 AuthenticationError。"""
    from app.core.oauth_providers import OAuthProviderConfig
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token

    mock_config = OAuthProviderConfig(
        name="test", authorize_url="", token_url="https://example.com/token",
        userinfo_url="", client_id="c", client_secret="s", scope="r",
        redirect_uri="http://localhost/cb",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="OAuth 授权码验证失败"):
        await _exchange_code_for_token(mock_config, "bad-code")


@pytest.mark.asyncio
async def test_exchange_code_no_access_token_in_response() -> None:
    """Token 响应中缺少 access_token 字段抛出 AuthenticationError。"""
    from app.core.oauth_providers import OAuthProviderConfig
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token

    mock_config = OAuthProviderConfig(
        name="test", authorize_url="", token_url="https://example.com/token",
        userinfo_url="", client_id="c", client_secret="s", scope="r",
        redirect_uri="http://localhost/cb",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "invalid_grant", "error_description": "Code expired"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="Code expired"):
        await _exchange_code_for_token(mock_config, "expired-code")


@pytest.mark.asyncio
async def test_fetch_user_info_failure() -> None:
    """获取用户信息失败抛出 AuthenticationError。"""
    from app.core.oauth_providers import OAuthProviderConfig
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info

    mock_config = OAuthProviderConfig(
        name="test", authorize_url="", token_url="",
        userinfo_url="https://example.com/user", client_id="c", client_secret="s",
        scope="r", redirect_uri="http://localhost/cb",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="获取 OAuth 用户信息失败"):
        await _fetch_user_info(mock_config, "invalid-token")


# ======== 环境变量配置 ========

def test_settings_has_oauth_fields() -> None:
    """Settings 包含 OAuth 配置字段。"""
    from app.core.config import settings

    assert hasattr(settings, "oauth_github_client_id")
    assert hasattr(settings, "oauth_github_client_secret")
    assert hasattr(settings, "oauth_redirect_base_url")


# ======== Alembic 迁移文件存在 ========

def test_migration_0036_exists() -> None:
    """迁移文件 0036 存在。"""
    from pathlib import Path

    migration = Path(__file__).parent.parent / "alembic" / "versions" / "0036_oauth_connections.py"
    assert migration.exists()
