"""OAuth 2.0 认证 API 测试。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.main import app


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """生成一个已登录用户的 JWT header。"""
    token = create_access_token(data={"sub": str(uuid.uuid4()), "role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _make_config(name: str = "github") -> "OAuthProviderConfig":
    """创建测试用 OAuthProviderConfig。"""
    from app.core.oauth_providers import OAuthProviderConfig

    urls = {
        "github": {
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "scope": "read:user,user:email",
        },
        "wecom": {
            "authorize_url": "https://login.work.weixin.qq.com/wwlogin/sso/login",
            "token_url": "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            "userinfo_url": "https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo",
            "client_id": "ww-corp-id",
            "client_secret": "ww-secret",
            "scope": "",
        },
        "dingtalk": {
            "authorize_url": "https://login.dingtalk.com/oauth2/auth",
            "token_url": "https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
            "userinfo_url": "https://api.dingtalk.com/v1.0/contact/users/me",
            "client_id": "dt-client-id",
            "client_secret": "dt-secret",
            "scope": "openid",
        },
        "feishu": {
            "authorize_url": "https://open.feishu.cn/open-apis/authen/v1/authorize",
            "token_url": "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
            "userinfo_url": "https://open.feishu.cn/open-apis/authen/v1/user_info",
            "client_id": "fs-app-id",
            "client_secret": "fs-app-secret",
            "scope": "",
        },
        "oidc": {
            "authorize_url": "https://idp.example.com/auth",
            "token_url": "https://idp.example.com/token",
            "userinfo_url": "https://idp.example.com/userinfo",
            "client_id": "oidc-client-id",
            "client_secret": "oidc-secret",
            "scope": "openid profile email",
        },
        "google": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            "client_id": "google-client-id",
            "client_secret": "google-secret",
            "scope": "openid profile email",
        },
    }
    u = urls[name]
    return OAuthProviderConfig(
        name=name,
        authorize_url=u["authorize_url"],
        token_url=u["token_url"],
        userinfo_url=u["userinfo_url"],
        client_id=u["client_id"],
        client_secret=u["client_secret"],
        scope=u["scope"],
        redirect_uri=f"http://localhost:3000/oauth/callback/{name}",
    )


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
    mock_config = _make_config("github")

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
    mock_config = _make_config("github")

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
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token

    mock_config = _make_config("github")

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
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token

    mock_config = _make_config("github")

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
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info

    mock_config = _make_config("github")

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


# ======== 企微 (WeCom) Provider ========


def test_wecom_provider_unconfigured() -> None:
    """未配置企微时返回 None。"""
    from app.core.oauth_providers import get_wecom_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_wecom_corp_id = ""
        mock_settings.oauth_wecom_secret = ""
        assert get_wecom_provider() is None


def test_wecom_provider_configured() -> None:
    """配置企微后返回正确 config。"""
    from app.core.oauth_providers import get_wecom_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_wecom_corp_id = "ww-corp-id"
        mock_settings.oauth_wecom_secret = "ww-secret"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"
        cfg = get_wecom_provider()
        assert cfg is not None
        assert cfg.name == "wecom"
        assert cfg.client_id == "ww-corp-id"


def test_wecom_authorize_url_format() -> None:
    """企微授权 URL 包含 login_type=CorpApp 和 appid。"""
    from app.services.oauth_service import _build_authorize_url_wecom

    config = _make_config("wecom")
    with patch("app.services.oauth_service.settings") as mock_settings:
        mock_settings.oauth_wecom_agent_id = "1000001"
        url = _build_authorize_url_wecom(config, "test-state")

    assert "login_type=CorpApp" in url
    assert "appid=ww-corp-id" in url
    assert "agentid=1000001" in url
    assert "state=test-state" in url


@pytest.mark.asyncio
async def test_wecom_exchange_code_success() -> None:
    """企微 token 交换成功。"""
    from app.services.oauth_service import _exchange_code_for_token_wecom

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 0, "access_token": "corp-token-123"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        token = await _exchange_code_for_token_wecom(config, "test-code")
    assert token == "corp-token-123"


@pytest.mark.asyncio
async def test_wecom_exchange_code_errcode() -> None:
    """企微 token 交换 errcode 非零抛出异常。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token_wecom

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 40013, "errmsg": "invalid corpid"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="invalid corpid"):
        await _exchange_code_for_token_wecom(config, "bad-code")


@pytest.mark.asyncio
async def test_wecom_fetch_user_info_success() -> None:
    """企微用户信息获取成功（两步请求）。"""
    from app.services.oauth_service import _fetch_user_info_wecom

    identity_resp = MagicMock()
    identity_resp.status_code = 200
    identity_resp.json.return_value = {"errcode": 0, "userid": "zhangsan"}

    detail_resp = MagicMock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = {
        "errcode": 0,
        "name": "张三",
        "email": "zhangsan@corp.com",
        "avatar": "https://wework.qpic.cn/avatar.jpg",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[identity_resp, detail_resp])

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_wecom(config, "corp-token", "auth-code")

    assert info["id"] == "zhangsan"
    assert info["name"] == "张三"
    assert info["email"] == "zhangsan@corp.com"


@pytest.mark.asyncio
async def test_wecom_fetch_user_info_detail_fallback() -> None:
    """企微用户详情请求失败降级到基础身份信息。"""
    from app.services.oauth_service import _fetch_user_info_wecom

    identity_resp = MagicMock()
    identity_resp.status_code = 200
    identity_resp.json.return_value = {"errcode": 0, "userid": "lisi"}

    detail_resp = MagicMock()
    detail_resp.status_code = 500

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[identity_resp, detail_resp])

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_wecom(config, "corp-token", "code")

    assert info["id"] == "lisi"
    assert info["name"] == "lisi"


@pytest.mark.asyncio
async def test_wecom_fetch_user_info_no_userid() -> None:
    """企微未返回 userid 抛出异常。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_wecom

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"errcode": 0}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=resp)

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="企微未返回用户 ID"):
        await _fetch_user_info_wecom(config, "token", "code")


# ======== 钉钉 (DingTalk) Provider ========


def test_dingtalk_provider_unconfigured() -> None:
    """未配置钉钉时返回 None。"""
    from app.core.oauth_providers import get_dingtalk_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_dingtalk_client_id = ""
        mock_settings.oauth_dingtalk_client_secret = ""
        assert get_dingtalk_provider() is None


def test_dingtalk_provider_configured() -> None:
    """配置钉钉后返回正确 config。"""
    from app.core.oauth_providers import get_dingtalk_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_dingtalk_client_id = "dt-client"
        mock_settings.oauth_dingtalk_client_secret = "dt-secret"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"
        cfg = get_dingtalk_provider()
        assert cfg is not None
        assert cfg.name == "dingtalk"


def test_dingtalk_authorize_url_format() -> None:
    """钉钉授权 URL 包含 response_type=code 和 prompt=consent。"""
    from app.services.oauth_service import _build_authorize_url_dingtalk

    config = _make_config("dingtalk")
    url = _build_authorize_url_dingtalk(config, "test-state")

    assert "response_type=code" in url
    assert "prompt=consent" in url
    assert f"client_id={config.client_id}" in url


@pytest.mark.asyncio
async def test_dingtalk_exchange_code_success() -> None:
    """钉钉 token 交换成功（JSON body）。"""
    from app.services.oauth_service import _exchange_code_for_token_dingtalk

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"accessToken": "dt-user-token-456"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    config = _make_config("dingtalk")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        token = await _exchange_code_for_token_dingtalk(config, "test-code")
    assert token == "dt-user-token-456"

    # 验证 JSON body 格式
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["json"]["clientId"] == "dt-client-id"
    assert call_kwargs.kwargs["json"]["grantType"] == "authorization_code"


@pytest.mark.asyncio
async def test_dingtalk_exchange_code_failure() -> None:
    """钉钉 token 交换失败。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token_dingtalk

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": "invalid code"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    config = _make_config("dingtalk")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="invalid code"):
        await _exchange_code_for_token_dingtalk(config, "bad")


@pytest.mark.asyncio
async def test_dingtalk_fetch_user_info_success() -> None:
    """钉钉用户信息获取成功。"""
    from app.services.oauth_service import _fetch_user_info_dingtalk

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "openId": "dt-open-123",
        "nick": "张三",
        "email": "zhangsan@corp.com",
        "avatarUrl": "https://st.dingtalk.com/avatar.jpg",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("dingtalk")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_dingtalk(config, "dt-token", "code")

    assert info["id"] == "dt-open-123"
    assert info["name"] == "张三"
    assert info["avatar_url"] == "https://st.dingtalk.com/avatar.jpg"

    # 验证 header
    call_kwargs = mock_client.get.call_args
    assert call_kwargs.kwargs["headers"]["x-acs-dingtalk-access-token"] == "dt-token"


@pytest.mark.asyncio
async def test_dingtalk_fetch_user_info_failure() -> None:
    """钉钉用户信息获取失败。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_dingtalk

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("dingtalk")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="获取钉钉用户信息失败"):
        await _fetch_user_info_dingtalk(config, "bad-token", "code")


# ======== 飞书 (Feishu) Provider ========


def test_feishu_provider_unconfigured() -> None:
    """未配置飞书时返回 None。"""
    from app.core.oauth_providers import get_feishu_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_feishu_app_id = ""
        mock_settings.oauth_feishu_app_secret = ""
        assert get_feishu_provider() is None


def test_feishu_provider_configured() -> None:
    """配置飞书后返回正确 config。"""
    from app.core.oauth_providers import get_feishu_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_feishu_app_id = "fs-app-id"
        mock_settings.oauth_feishu_app_secret = "fs-secret"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"
        cfg = get_feishu_provider()
        assert cfg is not None
        assert cfg.name == "feishu"


def test_feishu_authorize_url_format() -> None:
    """飞书授权 URL 使用 app_id 而非 client_id。"""
    from app.services.oauth_service import _build_authorize_url_feishu

    config = _make_config("feishu")
    url = _build_authorize_url_feishu(config, "test-state")

    assert "app_id=fs-app-id" in url
    assert "state=test-state" in url
    assert "client_id" not in url


@pytest.mark.asyncio
async def test_feishu_exchange_code_success() -> None:
    """飞书 token 交换成功（两步：app_token → user_token）。"""
    from app.services.oauth_service import _exchange_code_for_token_feishu

    # app_access_token 响应
    app_resp = MagicMock()
    app_resp.status_code = 200
    app_resp.json.return_value = {"app_access_token": "app-token-abc"}

    # user_access_token 响应
    user_resp = MagicMock()
    user_resp.status_code = 200
    user_resp.json.return_value = {"data": {"access_token": "user-token-xyz"}}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=[app_resp, user_resp])

    config = _make_config("feishu")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        token = await _exchange_code_for_token_feishu(config, "test-code")
    assert token == "user-token-xyz"


# ======== OIDC (Keycloak / Casdoor / 通用) Provider ========


# --- Discovery ---


_DISCOVERY_RESPONSE = {
    "issuer": "https://idp.example.com",
    "authorization_endpoint": "https://idp.example.com/auth",
    "token_endpoint": "https://idp.example.com/token",
    "userinfo_endpoint": "https://idp.example.com/userinfo",
    "jwks_uri": "https://idp.example.com/certs",
}


def _reset_oidc_cache() -> None:
    """重置 OIDC Discovery 缓存，保证测试隔离。"""
    import app.core.oauth_providers as mod
    mod._oidc_discovery_cache = None


def test_oidc_discovery_success() -> None:
    """OIDC Discovery 成功返回并缓存端点。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _DISCOVERY_RESPONSE.copy()

    with patch("app.core.oauth_providers.httpx.get", return_value=mock_resp) as mock_get:
        result = _discover_oidc_endpoints("https://idp.example.com")

    assert result is not None
    assert result["authorization_endpoint"] == "https://idp.example.com/auth"
    assert result["token_endpoint"] == "https://idp.example.com/token"
    mock_get.assert_called_once()
    _reset_oidc_cache()


def test_oidc_discovery_cache_hit() -> None:
    """第二次调用命中缓存，不发请求。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _DISCOVERY_RESPONSE.copy()

    with patch("app.core.oauth_providers.httpx.get", return_value=mock_resp) as mock_get:
        _discover_oidc_endpoints("https://idp.example.com")
        # 第二次调用应命中缓存
        result2 = _discover_oidc_endpoints("https://idp.example.com")

    assert result2 is not None
    mock_get.assert_called_once()  # 只请求了一次
    _reset_oidc_cache()


def test_oidc_discovery_http_error() -> None:
    """OIDC Discovery 网络异常返回 None。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    with patch("app.core.oauth_providers.httpx.get", side_effect=httpx.ConnectError("timeout")):
        result = _discover_oidc_endpoints("https://idp.example.com")

    assert result is None
    _reset_oidc_cache()


def test_oidc_discovery_non_200() -> None:
    """OIDC Discovery 返回非 200 状态码时返回 None。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("app.core.oauth_providers.httpx.get", return_value=mock_resp):
        result = _discover_oidc_endpoints("https://idp.example.com")

    assert result is None
    _reset_oidc_cache()


def test_oidc_discovery_missing_required_field() -> None:
    """Discovery 响应缺少 token_endpoint 时返回 None。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    incomplete = {"authorization_endpoint": "https://idp.example.com/auth"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = incomplete

    with patch("app.core.oauth_providers.httpx.get", return_value=mock_resp):
        result = _discover_oidc_endpoints("https://idp.example.com")

    assert result is None
    _reset_oidc_cache()


def test_oidc_discovery_issuer_trailing_slash() -> None:
    """Issuer URL 带尾部斜杠时正确拼接。"""
    from app.core.oauth_providers import _discover_oidc_endpoints

    _reset_oidc_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _DISCOVERY_RESPONSE.copy()

    with patch("app.core.oauth_providers.httpx.get", return_value=mock_resp) as mock_get:
        _discover_oidc_endpoints("https://idp.example.com/")

    # 应该去重尾部斜杠：不会出现 //
    called_url = mock_get.call_args[0][0]
    assert "//" not in called_url.replace("https://", "")
    _reset_oidc_cache()


# --- Provider Factory ---


def test_oidc_provider_unconfigured() -> None:
    """未配置 OIDC issuer 时返回 None。"""
    from app.core.oauth_providers import get_oidc_provider

    _reset_oidc_cache()
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_oidc_issuer = ""
        mock_settings.oauth_oidc_client_id = ""
        assert get_oidc_provider() is None
    _reset_oidc_cache()


def test_oidc_provider_no_client_id() -> None:
    """仅配置 issuer 但缺少 client_id 时返回 None。"""
    from app.core.oauth_providers import get_oidc_provider

    _reset_oidc_cache()
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_oidc_issuer = "https://idp.example.com"
        mock_settings.oauth_oidc_client_id = ""
        assert get_oidc_provider() is None
    _reset_oidc_cache()


def test_oidc_provider_discovery_fails() -> None:
    """配置了 OIDC 但 Discovery 失败时返回 None。"""
    from app.core.oauth_providers import get_oidc_provider

    _reset_oidc_cache()
    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.oauth_providers.httpx.get", side_effect=httpx.ConnectError("fail")):
        mock_settings.oauth_oidc_issuer = "https://idp.example.com"
        mock_settings.oauth_oidc_client_id = "oidc-id"
        assert get_oidc_provider() is None
    _reset_oidc_cache()


def test_oidc_provider_configured_success() -> None:
    """OIDC 配置完整 + Discovery 成功时返回正确 config。"""
    from app.core.oauth_providers import get_oidc_provider

    _reset_oidc_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _DISCOVERY_RESPONSE.copy()

    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.oauth_providers.httpx.get", return_value=mock_resp):
        mock_settings.oauth_oidc_issuer = "https://idp.example.com"
        mock_settings.oauth_oidc_client_id = "oidc-id"
        mock_settings.oauth_oidc_client_secret = "oidc-secret"
        mock_settings.oauth_oidc_scope = "openid profile email"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"

        cfg = get_oidc_provider()
        assert cfg is not None
        assert cfg.name == "oidc"
        assert cfg.authorize_url == "https://idp.example.com/auth"
        assert cfg.token_url == "https://idp.example.com/token"
        assert cfg.userinfo_url == "https://idp.example.com/userinfo"
        assert cfg.client_id == "oidc-id"
        assert cfg.scope == "openid profile email"
    _reset_oidc_cache()


def test_oidc_provider_fallback_userinfo() -> None:
    """Discovery 响应缺少 userinfo_endpoint 时用 issuer/userinfo 兜底。"""
    from app.core.oauth_providers import get_oidc_provider

    _reset_oidc_cache()
    disc = {
        "authorization_endpoint": "https://idp.example.com/auth",
        "token_endpoint": "https://idp.example.com/token",
        # 无 userinfo_endpoint
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = disc

    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.oauth_providers.httpx.get", return_value=mock_resp):
        mock_settings.oauth_oidc_issuer = "https://idp.example.com"
        mock_settings.oauth_oidc_client_id = "oidc-id"
        mock_settings.oauth_oidc_client_secret = "oidc-secret"
        mock_settings.oauth_oidc_scope = "openid"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"

        cfg = get_oidc_provider()
        assert cfg is not None
        assert cfg.userinfo_url == "https://idp.example.com/userinfo"
    _reset_oidc_cache()


# --- Authorize URL ---


def test_oidc_authorize_url_has_response_type_code() -> None:
    """OIDC 授权 URL 必须包含 response_type=code。"""
    from app.services.oauth_service import _build_authorize_url_oidc

    config = _make_config("oidc")
    url = _build_authorize_url_oidc(config, "test-state")

    assert "response_type=code" in url
    assert "client_id=oidc-client-id" in url
    assert "state=test-state" in url
    assert "scope=openid" in url


def test_oidc_authorize_url_redirect_uri() -> None:
    """OIDC 授权 URL 包含正确的 redirect_uri。"""
    from app.services.oauth_service import _build_authorize_url_oidc

    config = _make_config("oidc")
    url = _build_authorize_url_oidc(config, "s")
    assert "redirect_uri=" in url


# --- UserInfo ---


@pytest.mark.asyncio
async def test_oidc_fetch_userinfo_success() -> None:
    """OIDC UserInfo 成功：标准字段映射为内部格式。"""
    from app.services.oauth_service import _fetch_user_info_oidc

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "sub": "uuid-123",
        "preferred_username": "john",
        "name": "John Doe",
        "email": "john@example.com",
        "picture": "https://example.com/avatar.png",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("oidc")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_oidc(config, "access-token", "code")

    assert info["id"] == "uuid-123"
    assert info["login"] == "john"
    assert info["name"] == "John Doe"
    assert info["email"] == "john@example.com"
    assert info["avatar_url"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_oidc_fetch_userinfo_minimal() -> None:
    """OIDC UserInfo 最小响应：仅 sub 字段，其余回退空串。"""
    from app.services.oauth_service import _fetch_user_info_oidc

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"sub": "user-456"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("oidc")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_oidc(config, "token", "code")

    assert info["id"] == "user-456"
    assert info["login"] == ""  # no preferred_username
    assert info["name"] == ""   # no name
    assert info["email"] == ""
    assert info["avatar_url"] == ""


@pytest.mark.asyncio
async def test_oidc_fetch_userinfo_http_error() -> None:
    """OIDC UserInfo 网络异常时抛出 AuthenticationError。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_oidc

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    config = _make_config("oidc")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="OIDC"):
        await _fetch_user_info_oidc(config, "token", "code")


@pytest.mark.asyncio
async def test_oidc_fetch_userinfo_non_200() -> None:
    """OIDC UserInfo 返回 401 时抛出 AuthenticationError。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_oidc

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("oidc")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="OIDC"):
        await _fetch_user_info_oidc(config, "bad-token", "code")


# --- OIDC Token 交换（使用默认标准流程） ---


@pytest.mark.asyncio
async def test_oidc_token_exchange_uses_default_flow() -> None:
    """OIDC token 交换应使用默认 OAuth 2.0 标准 form-encoded 流程。"""
    from app.services.oauth_service import _CUSTOM_TOKEN_EXCHANGERS

    # OIDC 不应有自定义 token 交换器
    assert "oidc" not in _CUSTOM_TOKEN_EXCHANGERS


# --- OIDC 分发表注册检查 ---


def test_oidc_registered_in_dispatch_tables() -> None:
    """OIDC 在授权 URL 和用户信息分发表中已注册。"""
    from app.services.oauth_service import (
        _CUSTOM_AUTHORIZE_BUILDERS,
        _CUSTOM_USERINFO_FETCHERS,
    )

    assert "oidc" in _CUSTOM_AUTHORIZE_BUILDERS
    assert "oidc" in _CUSTOM_USERINFO_FETCHERS


def test_oidc_in_provider_factories() -> None:
    """OIDC 已注册到 Provider 工厂。"""
    from app.core.oauth_providers import _PROVIDER_FACTORIES

    assert "oidc" in _PROVIDER_FACTORIES


# ======== Google OAuth Provider ========


def test_google_provider_unconfigured() -> None:
    """未配置 Google 时返回 None。"""
    from app.core.oauth_providers import get_google_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_google_client_id = ""
        mock_settings.oauth_google_client_secret = ""
        assert get_google_provider() is None


def test_google_provider_configured() -> None:
    """配置 Google 后返回正确 config。"""
    from app.core.oauth_providers import get_google_provider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.oauth_google_client_id = "google-id"
        mock_settings.oauth_google_client_secret = "google-secret"
        mock_settings.oauth_google_scope = "openid profile email"
        mock_settings.oauth_redirect_base_url = "http://localhost:3000"
        cfg = get_google_provider()
        assert cfg is not None
        assert cfg.name == "google"
        assert cfg.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth"
        assert cfg.token_url == "https://oauth2.googleapis.com/token"
        assert cfg.scope == "openid profile email"


def test_google_authorize_url_params() -> None:
    """Google 授权 URL 包含 response_type=code 和 access_type=offline。"""
    from app.services.oauth_service import _build_authorize_url_google

    config = _make_config("google")
    url = _build_authorize_url_google(config, "test-state")

    assert "response_type=code" in url
    assert "access_type=offline" in url
    assert "client_id=google-client-id" in url
    assert "state=test-state" in url
    assert "scope=openid" in url


def test_google_authorize_url_redirect_uri() -> None:
    """Google 授权 URL 包含 redirect_uri。"""
    from app.services.oauth_service import _build_authorize_url_google

    config = _make_config("google")
    url = _build_authorize_url_google(config, "s")
    assert "redirect_uri=" in url


@pytest.mark.asyncio
async def test_google_fetch_userinfo_success() -> None:
    """Google UserInfo 成功获取。"""
    from app.services.oauth_service import _fetch_user_info_google

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "1234567890",
        "name": "Jane Smith",
        "email": "jane@gmail.com",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("google")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_google(config, "access-token", "code")

    assert info["id"] == "1234567890"
    assert info["login"] == "jane@gmail.com"
    assert info["name"] == "Jane Smith"
    assert info["email"] == "jane@gmail.com"
    assert info["avatar_url"] == "https://lh3.googleusercontent.com/photo.jpg"


@pytest.mark.asyncio
async def test_google_fetch_userinfo_minimal() -> None:
    """Google UserInfo 最小响应：仅 id。"""
    from app.services.oauth_service import _fetch_user_info_google

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "999"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("google")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_google(config, "token", "code")

    assert info["id"] == "999"
    assert info["login"] == ""
    assert info["name"] == ""
    assert info["avatar_url"] == ""


@pytest.mark.asyncio
async def test_google_fetch_userinfo_http_error() -> None:
    """Google UserInfo 网络异常时抛出 AuthenticationError。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_google

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    config = _make_config("google")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="Google"):
        await _fetch_user_info_google(config, "token", "code")


@pytest.mark.asyncio
async def test_google_fetch_userinfo_non_200() -> None:
    """Google UserInfo 返回非 200 时抛出 AuthenticationError。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_google

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("google")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="Google"):
        await _fetch_user_info_google(config, "bad", "code")


def test_google_token_exchange_uses_default_flow() -> None:
    """Google token 交换应使用默认标准 OAuth 2.0 form-encoded 流程。"""
    from app.services.oauth_service import _CUSTOM_TOKEN_EXCHANGERS

    assert "google" not in _CUSTOM_TOKEN_EXCHANGERS


def test_google_registered_in_dispatch_tables() -> None:
    """Google 在授权 URL 和用户信息分发表中已注册。"""
    from app.services.oauth_service import (
        _CUSTOM_AUTHORIZE_BUILDERS,
        _CUSTOM_USERINFO_FETCHERS,
    )

    assert "google" in _CUSTOM_AUTHORIZE_BUILDERS
    assert "google" in _CUSTOM_USERINFO_FETCHERS


def test_google_in_provider_factories() -> None:
    """Google 已注册到 Provider 工厂。"""
    from app.core.oauth_providers import _PROVIDER_FACTORIES

    assert "google" in _PROVIDER_FACTORIES


@pytest.mark.asyncio
async def test_feishu_exchange_code_app_token_failure() -> None:
    """飞书 app_access_token 获取失败。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _exchange_code_for_token_feishu

    app_resp = MagicMock()
    app_resp.status_code = 200
    app_resp.json.return_value = {"msg": "invalid app_id"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=app_resp)

    config = _make_config("feishu")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="飞书 app_access_token 获取失败"):
        await _exchange_code_for_token_feishu(config, "code")


@pytest.mark.asyncio
async def test_feishu_fetch_user_info_success() -> None:
    """飞书用户信息获取成功。"""
    from app.services.oauth_service import _fetch_user_info_feishu

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "open_id": "ou_abc123",
            "name": "李四",
            "email": "lisi@corp.com",
            "avatar_url": "https://sf3-cn.feishucdn.com/avatar.jpg",
        }
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("feishu")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_feishu(config, "user-token", "code")

    assert info["id"] == "ou_abc123"
    assert info["name"] == "李四"
    assert info["email"] == "lisi@corp.com"


@pytest.mark.asyncio
async def test_feishu_fetch_user_info_avatar_nested() -> None:
    """飞书 avatar 字段嵌套在 dict 中时正确提取。"""
    from app.services.oauth_service import _fetch_user_info_feishu

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "open_id": "ou_xyz",
            "name": "王五",
            "email": "",
            "avatar": {"avatar_origin": "https://feishu.cn/big.jpg"},
        }
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("feishu")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info_feishu(config, "token", "code")

    assert info["avatar_url"] == "https://feishu.cn/big.jpg"


@pytest.mark.asyncio
async def test_feishu_fetch_user_info_failure() -> None:
    """飞书用户信息获取 HTTP 失败。"""
    from app.core.exceptions import AuthenticationError
    from app.services.oauth_service import _fetch_user_info_feishu

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    config = _make_config("feishu")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         pytest.raises(AuthenticationError, match="获取飞书用户信息失败"):
        await _fetch_user_info_feishu(config, "bad", "code")


# ======== Provider 分发表测试 ========


def test_dispatch_tables_registered() -> None:
    """分发表包含所有 Provider。"""
    from app.services.oauth_service import (
        _CUSTOM_AUTHORIZE_BUILDERS,
        _CUSTOM_TOKEN_EXCHANGERS,
        _CUSTOM_USERINFO_FETCHERS,
    )

    for provider in ("wecom", "dingtalk", "feishu"):
        assert provider in _CUSTOM_AUTHORIZE_BUILDERS, f"{provider} 未注册 authorize builder"
        assert provider in _CUSTOM_TOKEN_EXCHANGERS, f"{provider} 未注册 token exchanger"
        assert provider in _CUSTOM_USERINFO_FETCHERS, f"{provider} 未注册 userinfo fetcher"

    # GitHub 不在自定义表中（使用默认流程）
    assert "github" not in _CUSTOM_TOKEN_EXCHANGERS


@pytest.mark.asyncio
async def test_exchange_dispatches_to_custom() -> None:
    """_exchange_code_for_token 能正确分发到钉钉自定义实现。"""
    from app.services.oauth_service import _exchange_code_for_token

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"accessToken": "dispatched-token"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    config = _make_config("dingtalk")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        token = await _exchange_code_for_token(config, "code")
    assert token == "dispatched-token"


@pytest.mark.asyncio
async def test_fetch_dispatches_to_wecom_with_code() -> None:
    """_fetch_user_info 能正确分发到企微实现（传递 code）。"""
    from app.services.oauth_service import _fetch_user_info

    identity_resp = MagicMock()
    identity_resp.status_code = 200
    identity_resp.json.return_value = {"errcode": 0, "userid": "ww-user"}

    detail_resp = MagicMock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = {"errcode": 0, "name": "企微用户"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[identity_resp, detail_resp])

    config = _make_config("wecom")
    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        info = await _fetch_user_info(config, "token", code="auth-code")
    assert info["id"] == "ww-user"
    assert info["name"] == "企微用户"


# ======== Settings 新增字段 ========


def test_settings_has_new_oauth_fields() -> None:
    """Settings 包含企微/钉钉/飞书 OAuth 配置字段。"""
    from app.core.config import settings

    assert hasattr(settings, "oauth_wecom_corp_id")
    assert hasattr(settings, "oauth_wecom_agent_id")
    assert hasattr(settings, "oauth_wecom_secret")
    assert hasattr(settings, "oauth_dingtalk_client_id")
    assert hasattr(settings, "oauth_dingtalk_client_secret")
    assert hasattr(settings, "oauth_feishu_app_id")
    assert hasattr(settings, "oauth_feishu_app_secret")


# ======== Provider 列表扩展 ========


def test_provider_factories_include_all() -> None:
    """_PROVIDER_FACTORIES 包含四种 Provider。"""
    from app.core.oauth_providers import _PROVIDER_FACTORIES

    assert "github" in _PROVIDER_FACTORIES
    assert "wecom" in _PROVIDER_FACTORIES
    assert "dingtalk" in _PROVIDER_FACTORIES
    assert "feishu" in _PROVIDER_FACTORIES


@pytest.mark.asyncio
async def test_authorize_wecom_via_api() -> None:
    """通过 API 获取企微授权 URL。"""
    mock_config = _make_config("wecom")
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
             patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
             patch("app.services.oauth_service.settings") as mock_settings:
            mock_settings.oauth_wecom_agent_id = "1000001"
            resp = await ac.get("/api/v1/auth/oauth/wecom/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "authorize_url" in data
    assert "login_type=CorpApp" in data["authorize_url"]


@pytest.mark.asyncio
async def test_authorize_dingtalk_via_api() -> None:
    """通过 API 获取钉钉授权 URL。"""
    mock_config = _make_config("dingtalk")
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
             patch("app.services.oauth_service.get_redis", return_value=mock_redis):
            resp = await ac.get("/api/v1/auth/oauth/dingtalk/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "response_type=code" in data["authorize_url"]


@pytest.mark.asyncio
async def test_authorize_feishu_via_api() -> None:
    """通过 API 获取飞书授权 URL。"""
    mock_config = _make_config("feishu")
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
             patch("app.services.oauth_service.get_redis", return_value=mock_redis):
            resp = await ac.get("/api/v1/auth/oauth/feishu/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "app_id=fs-app-id" in data["authorize_url"]


# ======== handle_oauth_callback 全流程 ========


@pytest.mark.asyncio
async def test_handle_oauth_callback_success_new_user() -> None:
    """handle_oauth_callback: 新用户完整流程。"""
    from app.services.oauth_service import handle_oauth_callback

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")
    mock_config = _make_config("github")

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.role = "user"

    mock_db = AsyncMock()

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
         patch("app.services.oauth_service._exchange_code_for_token", return_value="access-token-123"), \
         patch("app.services.oauth_service._fetch_user_info", return_value={"id": "gh-123", "login": "testuser", "email": "t@e.com"}), \
         patch("app.services.oauth_service._find_or_create_user", return_value=mock_user):
        token = await handle_oauth_callback(mock_db, "github", "auth-code", "valid-state")

    assert token  # JWT 非空
    mock_redis.getdel.assert_called_once()


@pytest.mark.asyncio
async def test_handle_oauth_callback_invalid_state() -> None:
    """handle_oauth_callback: state 验证失败。"""
    from app.services.oauth_service import handle_oauth_callback

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)
    mock_db = AsyncMock()

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis):
        with pytest.raises(ValidationError, match="state 验证失败"):
            await handle_oauth_callback(mock_db, "github", "code", "bad-state")


@pytest.mark.asyncio
async def test_handle_oauth_callback_state_mismatch_provider() -> None:
    """handle_oauth_callback: state 对应的 provider 不匹配。"""
    from app.services.oauth_service import handle_oauth_callback

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="dingtalk")

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis):
        with pytest.raises(ValidationError, match="state 验证失败"):
            await handle_oauth_callback(AsyncMock(), "github", "code", "state-123")


@pytest.mark.asyncio
async def test_handle_oauth_callback_unconfigured_provider() -> None:
    """handle_oauth_callback: provider 未配置。"""
    from app.services.oauth_service import handle_oauth_callback

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="unknown")

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=None):
        with pytest.raises(ValidationError, match="不存在或未配置"):
            await handle_oauth_callback(AsyncMock(), "unknown", "code", "state")


# ======== bind_oauth_to_user ========


@pytest.mark.asyncio
async def test_bind_oauth_to_user_success_new_binding() -> None:
    """bind_oauth_to_user: 创建新绑定。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")
    mock_config = _make_config("github")

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
         patch("app.services.oauth_service._exchange_code_for_token", return_value="token-456"), \
         patch("app.services.oauth_service._fetch_user_info", return_value={"id": "gh-999", "login": "user1", "email": "u@e.com"}), \
         patch("app.services.oauth_service.encrypt_api_key", return_value="enc-token"):
        result = await bind_oauth_to_user(mock_db, mock_user, "github", "code", "state")

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_bind_oauth_to_user_already_bound_same_user() -> None:
    """bind_oauth_to_user: 已绑定到当前用户，直接返回。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")
    mock_config = _make_config("github")

    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id

    existing_conn = MagicMock()
    existing_conn.user_id = user_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_conn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
         patch("app.services.oauth_service._exchange_code_for_token", return_value="token"), \
         patch("app.services.oauth_service._fetch_user_info", return_value={"id": "gh-1", "login": "x"}):
        result = await bind_oauth_to_user(mock_db, mock_user, "github", "code", "state")

    assert result is existing_conn


@pytest.mark.asyncio
async def test_bind_oauth_to_user_conflict_other_user() -> None:
    """bind_oauth_to_user: 已绑定到其他用户，抛出冲突错误。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")
    mock_config = _make_config("github")

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    existing_conn = MagicMock()
    existing_conn.user_id = uuid.uuid4()  # 不同用户

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_conn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
         patch("app.services.oauth_service._exchange_code_for_token", return_value="token"), \
         patch("app.services.oauth_service._fetch_user_info", return_value={"id": "gh-1", "login": "x"}):
        with pytest.raises(ConflictError, match="已被其他用户绑定"):
            await bind_oauth_to_user(mock_db, mock_user, "github", "code", "state")


@pytest.mark.asyncio
async def test_bind_oauth_no_user_id() -> None:
    """bind_oauth_to_user: Provider 未返回 user id。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="github")
    mock_config = _make_config("github")

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=mock_config), \
         patch("app.services.oauth_service._exchange_code_for_token", return_value="token"), \
         patch("app.services.oauth_service._fetch_user_info", return_value={"login": "x"}):
        with pytest.raises(AuthenticationError, match="未返回用户 ID"):
            await bind_oauth_to_user(AsyncMock(), MagicMock(), "github", "code", "state")


@pytest.mark.asyncio
async def test_bind_oauth_invalid_state() -> None:
    """bind_oauth_to_user: state 验证失败（Redis 返回 None）。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis):
        with pytest.raises(ValidationError, match="state 验证失败"):
            await bind_oauth_to_user(AsyncMock(), MagicMock(), "github", "code", "bad-state")


@pytest.mark.asyncio
async def test_bind_oauth_unconfigured_provider() -> None:
    """bind_oauth_to_user: provider 未配置。"""
    from app.services.oauth_service import bind_oauth_to_user

    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="unknown")

    with patch("app.services.oauth_service.get_redis", return_value=mock_redis), \
         patch("app.services.oauth_service.get_provider_config", return_value=None):
        with pytest.raises(ValidationError, match="不存在或未配置"):
            await bind_oauth_to_user(AsyncMock(), MagicMock(), "unknown", "code", "state")


# ======== get_user_connections / unbind_oauth ========


@pytest.mark.asyncio
async def test_get_user_connections() -> None:
    """get_user_connections: 返回用户绑定列表。"""
    from app.services.oauth_service import get_user_connections

    mock_conn1 = MagicMock()
    mock_conn2 = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_conn1, mock_conn2]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_user_connections(mock_db, uuid.uuid4())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_unbind_oauth_success() -> None:
    """unbind_oauth: 成功解绑。"""
    from app.services.oauth_service import unbind_oauth

    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    await unbind_oauth(mock_db, mock_user, "github")
    mock_db.delete.assert_called_once_with(mock_conn)


@pytest.mark.asyncio
async def test_unbind_oauth_not_found() -> None:
    """unbind_oauth: 绑定不存在。"""
    from app.services.oauth_service import unbind_oauth

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(NotFoundError, match="未找到"):
        await unbind_oauth(mock_db, MagicMock(id=uuid.uuid4()), "github")


# ======== Provider 网络异常 ========


@pytest.mark.asyncio
async def test_wecom_exchange_network_error() -> None:
    """企微 token 交换网络异常。"""
    from app.services.oauth_service import _exchange_code_for_token_wecom
    config = _make_config("wecom")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="暂不可用"):
            await _exchange_code_for_token_wecom(config, "code")


@pytest.mark.asyncio
async def test_wecom_exchange_non_200() -> None:
    """企微 token 交换非 200 响应。"""
    from app.services.oauth_service import _exchange_code_for_token_wecom
    config = _make_config("wecom")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取失败"):
            await _exchange_code_for_token_wecom(config, "code")


@pytest.mark.asyncio
async def test_wecom_exchange_no_token() -> None:
    """企微响应缺少 access_token。"""
    from app.services.oauth_service import _exchange_code_for_token_wecom
    config = _make_config("wecom")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 0}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="缺少 access_token"):
            await _exchange_code_for_token_wecom(config, "code")


@pytest.mark.asyncio
async def test_wecom_userinfo_network_error() -> None:
    """企微用户信息获取网络异常。"""
    from app.services.oauth_service import _fetch_user_info_wecom
    config = _make_config("wecom")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="获取企微用户信息失败"):
            await _fetch_user_info_wecom(config, "token", "code")


@pytest.mark.asyncio
async def test_wecom_userinfo_non_200() -> None:
    """企微用户信息非 200 响应。"""
    from app.services.oauth_service import _fetch_user_info_wecom
    config = _make_config("wecom")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取企微用户身份失败"):
            await _fetch_user_info_wecom(config, "token", "code")


@pytest.mark.asyncio
async def test_wecom_userinfo_errcode() -> None:
    """企微用户信息 errcode 非 0。"""
    from app.services.oauth_service import _fetch_user_info_wecom
    config = _make_config("wecom")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"errcode": 42, "errmsg": "bad"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取企微用户身份失败"):
            await _fetch_user_info_wecom(config, "token", "code")


@pytest.mark.asyncio
async def test_dingtalk_exchange_network_error() -> None:
    """钉钉 token 交换网络异常。"""
    from app.services.oauth_service import _exchange_code_for_token_dingtalk
    config = _make_config("dingtalk")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="暂不可用"):
            await _exchange_code_for_token_dingtalk(config, "code")


@pytest.mark.asyncio
async def test_dingtalk_exchange_non_200() -> None:
    """钉钉 token 交换非 200 响应。"""
    from app.services.oauth_service import _exchange_code_for_token_dingtalk
    config = _make_config("dingtalk")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取失败"):
            await _exchange_code_for_token_dingtalk(config, "code")


@pytest.mark.asyncio
async def test_dingtalk_userinfo_network_error() -> None:
    """钉钉用户信息网络异常。"""
    from app.services.oauth_service import _fetch_user_info_dingtalk
    config = _make_config("dingtalk")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="获取钉钉用户信息失败"):
            await _fetch_user_info_dingtalk(config, "token", "code")


@pytest.mark.asyncio
async def test_feishu_exchange_network_error() -> None:
    """飞书 token 交换网络异常。"""
    from app.services.oauth_service import _exchange_code_for_token_feishu
    config = _make_config("feishu")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="暂不可用"):
            await _exchange_code_for_token_feishu(config, "code")


@pytest.mark.asyncio
async def test_feishu_exchange_user_token_non_200() -> None:
    """飞书 user_access_token 非 200。"""
    from app.services.oauth_service import _exchange_code_for_token_feishu
    config = _make_config("feishu")

    app_resp = MagicMock()
    app_resp.status_code = 200
    app_resp.json.return_value = {"app_access_token": "app-token"}

    user_resp = MagicMock()
    user_resp.status_code = 400

    with patch("httpx.AsyncClient.post", side_effect=[app_resp, user_resp]):
        with pytest.raises(AuthenticationError, match="user_access_token 获取失败"):
            await _exchange_code_for_token_feishu(config, "code")


@pytest.mark.asyncio
async def test_feishu_exchange_no_access_token() -> None:
    """飞书 user_access_token 响应缺少 token。"""
    from app.services.oauth_service import _exchange_code_for_token_feishu
    config = _make_config("feishu")

    app_resp = MagicMock()
    app_resp.status_code = 200
    app_resp.json.return_value = {"app_access_token": "app-tok"}

    user_resp = MagicMock()
    user_resp.status_code = 200
    user_resp.json.return_value = {"msg": "bad code"}

    with patch("httpx.AsyncClient.post", side_effect=[app_resp, user_resp]):
        with pytest.raises(AuthenticationError, match="user_access_token 获取失败"):
            await _exchange_code_for_token_feishu(config, "code")


@pytest.mark.asyncio
async def test_feishu_exchange_app_token_non_200() -> None:
    """飞书 app_access_token 请求非 200 状态码。"""
    from app.services.oauth_service import _exchange_code_for_token_feishu
    config = _make_config("feishu")

    app_resp = MagicMock()
    app_resp.status_code = 500

    with patch("httpx.AsyncClient.post", return_value=app_resp):
        with pytest.raises(AuthenticationError, match="飞书 app_access_token 获取失败"):
            await _exchange_code_for_token_feishu(config, "code")


@pytest.mark.asyncio
async def test_feishu_userinfo_network_error() -> None:
    """飞书用户信息网络异常。"""
    from app.services.oauth_service import _fetch_user_info_feishu
    config = _make_config("feishu")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="获取飞书用户信息失败"):
            await _fetch_user_info_feishu(config, "token", "code")


@pytest.mark.asyncio
async def test_feishu_userinfo_non_200() -> None:
    """飞书用户信息非 200。"""
    from app.services.oauth_service import _fetch_user_info_feishu
    config = _make_config("feishu")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取飞书用户信息失败"):
            await _fetch_user_info_feishu(config, "token", "code")


# ======== 默认 _exchange_code_for_token ========


@pytest.mark.asyncio
async def test_default_exchange_code_network_error() -> None:
    """默认 token 交换网络异常。"""
    from app.services.oauth_service import _exchange_code_for_token
    config = _make_config("github")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="暂不可用"):
            await _exchange_code_for_token(config, "code")


@pytest.mark.asyncio
async def test_default_exchange_code_non_200() -> None:
    """默认 token 交换非 200。"""
    from app.services.oauth_service import _exchange_code_for_token
    config = _make_config("github")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "bad request"

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="授权码验证失败"):
            await _exchange_code_for_token(config, "code")


@pytest.mark.asyncio
async def test_default_exchange_code_no_token() -> None:
    """默认 token 交换无 access_token。"""
    from app.services.oauth_service import _exchange_code_for_token
    config = _make_config("github")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "bad_verification_code", "error_description": "Bad code"}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="token 获取失败"):
            await _exchange_code_for_token(config, "code")


# ======== 默认 _fetch_user_info ========


@pytest.mark.asyncio
async def test_default_fetch_userinfo_network_error() -> None:
    """默认 userinfo 获取网络异常。"""
    from app.services.oauth_service import _fetch_user_info
    config = _make_config("github")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(AuthenticationError, match="获取 OAuth 用户信息失败"):
            await _fetch_user_info(config, "token")


@pytest.mark.asyncio
async def test_default_fetch_userinfo_non_200() -> None:
    """默认 userinfo 获取非 200。"""
    from app.services.oauth_service import _fetch_user_info
    config = _make_config("github")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取 OAuth 用户信息失败"):
            await _fetch_user_info(config, "token")


@pytest.mark.asyncio
async def test_default_fetch_userinfo_success() -> None:
    """默认 userinfo 成功获取。"""
    from app.services.oauth_service import _fetch_user_info
    config = _make_config("github")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 123, "login": "ghuser", "email": "gh@e.com"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        info = await _fetch_user_info(config, "token")
    assert info["id"] == 123
    assert info["login"] == "ghuser"


# ======== _find_or_create_user ========


@pytest.mark.asyncio
async def test_find_or_create_user_existing_binding() -> None:
    """_find_or_create_user: 已有绑定 → 返回关联用户。"""
    from app.services.oauth_service import _find_or_create_user

    user_id = uuid.uuid4()
    mock_conn = MagicMock()
    mock_conn.user_id = user_id
    mock_conn.access_token_encrypted = ""
    mock_conn.provider_username = ""
    mock_conn.provider_avatar_url = ""

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_active = True

    # 第一次 execute → 查 OAuthConnection → 有
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = mock_conn
    # 第二次 execute → 查 User → 有
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = mock_user

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2])
    mock_db.commit = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        user = await _find_or_create_user(
            mock_db, "github", {"id": "gh-1", "login": "u", "avatar_url": "a"}, "token"
        )

    assert user is mock_user


@pytest.mark.asyncio
async def test_find_or_create_user_existing_binding_user_disabled() -> None:
    """_find_or_create_user: 已有绑定但用户停用 → 抛出异常。"""
    from app.services.oauth_service import _find_or_create_user

    mock_conn = MagicMock()
    mock_conn.user_id = uuid.uuid4()
    mock_conn.access_token_encrypted = ""
    mock_conn.provider_username = ""
    mock_conn.provider_avatar_url = ""

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = mock_conn
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None  # 用户不存在/停用

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2])
    mock_db.commit = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        with pytest.raises(AuthenticationError, match="已停用"):
            await _find_or_create_user(
                mock_db, "github", {"id": "gh-1", "login": "u"}, "token"
            )


@pytest.mark.asyncio
async def test_find_or_create_user_email_match() -> None:
    """_find_or_create_user: 无绑定但邮箱匹配 → 自动绑定。"""
    from app.services.oauth_service import _find_or_create_user

    existing_user = MagicMock()
    existing_user.id = uuid.uuid4()
    existing_user.avatar_url = None

    # 第一次 execute → 查 OAuthConnection → 无
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = None
    # 第二次 execute → 查 email 匹配 → 有
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        user = await _find_or_create_user(
            mock_db, "github",
            {"id": "gh-2", "login": "u2", "email": "match@e.com", "avatar_url": "https://img.com/a.png"},
            "token",
        )

    assert user is existing_user
    assert existing_user.avatar_url == "https://img.com/a.png"


@pytest.mark.asyncio
async def test_find_or_create_user_new_user() -> None:
    """_find_or_create_user: 无绑定无邮箱匹配 → 创建新用户。"""
    from app.services.oauth_service import _find_or_create_user

    # 查 OAuthConnection → 无
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = None
    # 查 email → 无
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    # 查 username 唯一性 → 无冲突
    result3 = MagicMock()
    result3.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2, result3])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        user = await _find_or_create_user(
            mock_db, "github",
            {"id": "gh-3", "login": "newuser", "email": "new@e.com", "avatar_url": ""},
            "token",
        )

    assert user.username == "newuser"
    assert mock_db.add.call_count == 2  # user + conn


@pytest.mark.asyncio
async def test_find_or_create_user_username_conflict_retry() -> None:
    """_find_or_create_user: 用户名冲突后重试。"""
    from app.services.oauth_service import _find_or_create_user

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = None  # 无绑定
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None  # 无邮箱匹配
    result_conflict = MagicMock()
    result_conflict.scalar_one_or_none.return_value = MagicMock()  # 用户名已存在
    result_ok = MagicMock()
    result_ok.scalar_one_or_none.return_value = None  # 带后缀的用户名可用

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2, result_conflict, result_ok])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        user = await _find_or_create_user(
            mock_db, "github",
            {"id": "gh-4", "login": "taken", "email": "taken@e.com"},
            "token",
        )

    # User 构建时 username 应带后缀 _1（首次冲突）
    assert user.username == "taken_1"


@pytest.mark.asyncio
async def test_find_or_create_user_no_id() -> None:
    """_find_or_create_user: Provider 未返回 id。"""
    from app.services.oauth_service import _find_or_create_user

    with pytest.raises(AuthenticationError, match="未返回用户 ID"):
        await _find_or_create_user(AsyncMock(), "github", {"login": "x"}, "token")


@pytest.mark.asyncio
async def test_find_or_create_user_integrity_error() -> None:
    """_find_or_create_user: flush 时唯一约束冲突。"""
    from sqlalchemy.exc import IntegrityError
    from app.services.oauth_service import _find_or_create_user

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = None
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    result3 = MagicMock()
    result3.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2, result3])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
    mock_db.rollback = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        with pytest.raises(ConflictError, match="已被注册"):
            await _find_or_create_user(
                mock_db, "github",
                {"id": "gh-5", "login": "conflict_user", "email": "c@e.com"},
                "token",
            )


@pytest.mark.asyncio
async def test_find_or_create_user_no_email() -> None:
    """_find_or_create_user: 无邮箱时跳过邮箱匹配。"""
    from app.services.oauth_service import _find_or_create_user

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = None  # 无绑定
    # 无邮箱时直接跳到 username 检查
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[result1, result2])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.oauth_service.encrypt_api_key", return_value="enc"):
        user = await _find_or_create_user(
            mock_db, "github",
            {"id": "gh-noemail", "login": "noemail_user"},
            "token",
        )

    assert user.username == "noemail_user"
    # email 应生成 fallback
    assert "oauth.github" in user.email


@pytest.mark.asyncio
async def test_find_or_create_user_max_username_retries() -> None:
    """_find_or_create_user: 用户名重试超过最大次数。"""
    from app.services.oauth_service import _find_or_create_user

    result_no_binding = MagicMock()
    result_no_binding.scalar_one_or_none.return_value = None
    result_no_email = MagicMock()
    result_no_email.scalar_one_or_none.return_value = None
    # 每次检查用户名都发现已存在
    result_conflict = MagicMock()
    result_conflict.scalar_one_or_none.return_value = MagicMock()

    mock_db = AsyncMock()
    # 第 1 次=绑定查询 None, 第 2 次=邮箱查询 None, 之后全冲突
    mock_db.execute = AsyncMock(
        side_effect=[result_no_binding, result_no_email] + [result_conflict] * 101
    )

    with pytest.raises(ConflictError, match="无法生成唯一用户名"):
        await _find_or_create_user(
            mock_db, "github",
            {"id": "gh-max", "login": "popular", "email": "p@e.com"},
            "token",
        )


# ======== OIDC userinfo 非 200 ========


@pytest.mark.asyncio
async def test_oidc_fetch_userinfo_status_error() -> None:
    """OIDC userinfo 非 200 带日志。"""
    from app.services.oauth_service import _fetch_user_info_oidc
    config = _make_config("oidc")

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取 OIDC 用户信息失败"):
            await _fetch_user_info_oidc(config, "token", "code")


# ======== Google userinfo 非 200 ========


@pytest.mark.asyncio
async def test_google_fetch_userinfo_status_error() -> None:
    """Google userinfo 非 200 带日志。"""
    from app.services.oauth_service import _fetch_user_info_google
    config = _make_config("google")

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(AuthenticationError, match="获取 Google 用户信息失败"):
            await _fetch_user_info_google(config, "token", "code")
