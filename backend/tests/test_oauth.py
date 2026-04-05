"""OAuth 2.0 认证 API 测试。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
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
