"""认证 API 单元测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.main import app
from app.schemas.auth import (
    ChangePasswordRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "$2b$12$fake_hashed_password",
        "role": "user",
        "role_id": None,
        "is_active": True,
        "avatar_url": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestAuthSchemas:
    def test_register_valid(self) -> None:
        data = UserRegister(username="alice", email="alice@test.com", password="abcdef")
        assert data.username == "alice"
        assert data.email == "alice@test.com"

    def test_register_username_too_short(self) -> None:
        with pytest.raises(ValueError):
            UserRegister(username="ab", email="a@b.com", password="abcdef")

    def test_register_username_invalid_chars(self) -> None:
        with pytest.raises(ValueError):
            UserRegister(username="aa bb", email="a@b.com", password="abcdef")

    def test_register_email_invalid(self) -> None:
        with pytest.raises(ValueError):
            UserRegister(username="alice", email="notanemail", password="abcdef")

    def test_register_password_too_short(self) -> None:
        with pytest.raises(ValueError):
            UserRegister(username="alice", email="a@b.com", password="abc")

    def test_login_schema(self) -> None:
        data = UserLogin(username="alice", password="secret")
        assert data.username == "alice"

    def test_token_response(self) -> None:
        t = TokenResponse(access_token="tok123", expires_in=86400)
        assert t.token_type == "Bearer"
        assert t.refresh_token is None

    def test_token_response_with_refresh(self) -> None:
        t = TokenResponse(access_token="a", refresh_token="r", expires_in=86400)
        assert t.refresh_token == "r"

    def test_user_response_from_orm(self) -> None:
        user = _make_user()
        resp = UserResponse.model_validate(user, from_attributes=True)
        assert resp.username == "testuser"
        assert resp.email == "test@example.com"
        assert resp.role == "user"

    def test_register_email_normalized(self) -> None:
        data = UserRegister(username="alice", email="Alice@Test.COM", password="abcdef")
        assert data.email == "alice@test.com"

    def test_change_password_schema(self) -> None:
        data = ChangePasswordRequest(current_password="old", new_password="newpwd")
        assert data.current_password == "old"
        assert data.new_password == "newpwd"

    def test_change_password_new_too_short(self) -> None:
        with pytest.raises(ValueError):
            ChangePasswordRequest(current_password="old", new_password="ab")

    def test_refresh_token_schema(self) -> None:
        data = RefreshTokenRequest(refresh_token="some.token")
        assert data.refresh_token == "some.token"

    def test_password_reset_request_schema(self) -> None:
        data = PasswordResetRequest(email="a@b.com")
        assert data.email == "a@b.com"

    def test_password_reset_confirm_schema(self) -> None:
        data = PasswordResetConfirm(token="tok", new_password="newpwd")
        assert data.token == "tok"

    def test_password_reset_confirm_pwd_too_short(self) -> None:
        with pytest.raises(ValueError):
            PasswordResetConfirm(token="tok", new_password="ab")


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestAuthAPI:
    """认证 API 端点测试（使用 mock）。"""

    def _override_db(self) -> AsyncMock:
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        return mock_db

    def _cleanup(self) -> None:
        app.dependency_overrides.clear()

    # ── POST /api/v1/auth/register ──────────────────────────

    def test_register_success(self, client: TestClient) -> None:
        self._override_db()
        user = _make_user()
        try:
            with patch("app.api.auth.auth_service.register_user", new_callable=AsyncMock) as mock_reg:
                mock_reg.return_value = user
                resp = client.post("/api/v1/auth/register", json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": "secret123",
                })
                assert resp.status_code == 201
                body = resp.json()
                assert body["username"] == "testuser"
                assert body["email"] == "test@example.com"
                assert "hashed_password" not in body
        finally:
            self._cleanup()

    def test_register_conflict(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.register_user", new_callable=AsyncMock) as mock_reg:
                mock_reg.side_effect = ConflictError("用户名已存在")
                resp = client.post("/api/v1/auth/register", json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": "secret123",
                })
                assert resp.status_code == 409
        finally:
            self._cleanup()

    # ── POST /api/v1/auth/login ─────────────────────────────

    def test_login_success(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.authenticate_user", new_callable=AsyncMock) as mock_auth:
                mock_auth.return_value = ("fake.jwt.token", "fake.refresh.token")
                resp = client.post("/api/v1/auth/login", json={
                    "username": "testuser",
                    "password": "secret123",
                })
                assert resp.status_code == 200
                body = resp.json()
                assert body["access_token"] == "fake.jwt.token"
                assert body["refresh_token"] == "fake.refresh.token"
                assert body["token_type"] == "Bearer"
                assert body["expires_in"] > 0
        finally:
            self._cleanup()

    def test_login_invalid_credentials(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.authenticate_user", new_callable=AsyncMock) as mock_auth:
                mock_auth.side_effect = AuthenticationError("用户名或密码错误")
                resp = client.post("/api/v1/auth/login", json={
                    "username": "wrong",
                    "password": "wrong",
                })
                assert resp.status_code == 401
        finally:
            self._cleanup()

    # ── GET /api/v1/auth/me ─────────────────────────────────

    def test_me_success(self, client: TestClient) -> None:
        from app.core.deps import get_current_user

        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            body = resp.json()
            assert body["username"] == "testuser"
        finally:
            self._cleanup()

    def test_me_unauthenticated(self, client: TestClient) -> None:
        """无 Token 访问 /me 返回 401。"""
        from app.core.deps import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    # ── POST /api/v1/auth/refresh ───────────────────────────

    def test_refresh_success(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.refresh_access_token", new_callable=AsyncMock) as mock_ref:
                mock_ref.return_value = ("new.access", "new.refresh")
                resp = client.post("/api/v1/auth/refresh", json={
                    "refresh_token": "old.refresh.token",
                })
                assert resp.status_code == 200
                body = resp.json()
                assert body["access_token"] == "new.access"
                assert body["refresh_token"] == "new.refresh"
        finally:
            self._cleanup()

    def test_refresh_invalid(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.refresh_access_token", new_callable=AsyncMock) as mock_ref:
                mock_ref.side_effect = AuthenticationError("Refresh Token 无效或已过期")
                resp = client.post("/api/v1/auth/refresh", json={
                    "refresh_token": "bad.token",
                })
                assert resp.status_code == 401
        finally:
            self._cleanup()

    # ── POST /api/v1/auth/logout ────────────────────────────

    def test_logout_success(self, client: TestClient) -> None:
        from app.core.deps import get_current_user

        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch("app.api.auth.auth_service.logout_user", new_callable=AsyncMock) as mock_logout:
                resp = client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": "Bearer fake.token"},
                )
                assert resp.status_code == 204
                mock_logout.assert_called_once()
        finally:
            self._cleanup()

    # ── PUT /api/v1/auth/password ───────────────────────────

    def test_change_password_success(self, client: TestClient) -> None:
        from app.core.deps import get_current_user

        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.change_password", new_callable=AsyncMock) as mock_chg:
                resp = client.put("/api/v1/auth/password", json={
                    "current_password": "old123",
                    "new_password": "new456",
                })
                assert resp.status_code == 204
                mock_chg.assert_called_once()
        finally:
            self._cleanup()

    def test_change_password_wrong_current(self, client: TestClient) -> None:
        from app.core.deps import get_current_user

        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.change_password", new_callable=AsyncMock) as mock_chg:
                mock_chg.side_effect = AuthenticationError("当前密码错误")
                resp = client.put("/api/v1/auth/password", json={
                    "current_password": "wrong",
                    "new_password": "new456",
                })
                assert resp.status_code == 401
        finally:
            self._cleanup()

    # ── POST /api/v1/auth/password-reset/request ────────────

    def test_password_reset_request(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.request_password_reset", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = "reset-token-123"
                resp = client.post("/api/v1/auth/password-reset/request", json={
                    "email": "test@example.com",
                })
                assert resp.status_code == 200
                body = resp.json()
                assert "reset_token" in body
                assert body["reset_token"] == "reset-token-123"
        finally:
            self._cleanup()

    def test_password_reset_request_unknown_email(self, client: TestClient) -> None:
        """未知邮箱也返回 200（防枚举）。"""
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.request_password_reset", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = ""
                resp = client.post("/api/v1/auth/password-reset/request", json={
                    "email": "unknown@example.com",
                })
                assert resp.status_code == 200
        finally:
            self._cleanup()

    # ── POST /api/v1/auth/password-reset/confirm ────────────

    def test_password_reset_confirm_success(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.confirm_password_reset", new_callable=AsyncMock) as mock_cfm:
                resp = client.post("/api/v1/auth/password-reset/confirm", json={
                    "token": "valid-token",
                    "new_password": "newpwd123",
                })
                assert resp.status_code == 204
                mock_cfm.assert_called_once()
        finally:
            self._cleanup()

    def test_password_reset_confirm_invalid_token(self, client: TestClient) -> None:
        self._override_db()
        try:
            with patch("app.api.auth.auth_service.confirm_password_reset", new_callable=AsyncMock) as mock_cfm:
                mock_cfm.side_effect = AuthenticationError("重置令牌无效或已过期")
                resp = client.post("/api/v1/auth/password-reset/confirm", json={
                    "token": "bad-token",
                    "new_password": "newpwd123",
                })
                assert resp.status_code == 401
        finally:
            self._cleanup()


# ---------------------------------------------------------------------------
# Service 层测试
# ---------------------------------------------------------------------------


class TestAuthService:
    """认证服务层测试（mock DB + Redis）。"""

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self) -> None:
        from app.services.auth import change_password

        user = _make_user(hashed_password="$2b$12$somehash")
        db = AsyncMock()
        with patch("app.services.auth.verify_password", return_value=False), \
             pytest.raises(AuthenticationError, match="当前密码错误"):
            await change_password(db, user, "wrong", "newpwd")

    @pytest.mark.asyncio
    async def test_change_password_same_as_current(self) -> None:
        from app.services.auth import change_password

        user = _make_user()
        db = AsyncMock()
        with patch("app.services.auth.verify_password", return_value=True), \
             pytest.raises(ValidationError, match="新密码不能与当前密码相同"):
            await change_password(db, user, "same", "same")

    @pytest.mark.asyncio
    async def test_change_password_success(self) -> None:
        from app.services.auth import change_password

        user = _make_user()
        db = AsyncMock()
        with patch("app.services.auth.verify_password", return_value=True), \
             patch("app.services.auth.hash_password", return_value="$2b$12$newhash"):
            await change_password(db, user, "old", "newpwd")
            assert user.hashed_password == "$2b$12$newhash"
            db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirm_password_reset_invalid_token(self) -> None:
        from app.services.auth import confirm_password_reset

        db = AsyncMock()
        with patch("app.services.auth.validate_password_reset_token", new_callable=AsyncMock, return_value=None), \
             pytest.raises(AuthenticationError, match="重置令牌无效"):
            await confirm_password_reset(db, "bad-token", "newpwd")

    @pytest.mark.asyncio
    async def test_logout_user_blacklists_token(self) -> None:
        import time

        from app.services.auth import logout_user
        future_exp = int(time.time()) + 3600
        with patch("app.services.auth.decode_access_token", return_value={"sub": "uid", "exp": future_exp}), \
             patch("app.services.auth.blacklist_token", new_callable=AsyncMock) as mock_bl:
            await logout_user("access.token")
            mock_bl.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_access_token_blacklisted(self) -> None:
        from app.services.auth import refresh_access_token

        db = AsyncMock()
        with patch("app.services.auth.is_token_blacklisted", new_callable=AsyncMock, return_value=True), \
             pytest.raises(AuthenticationError, match="已失效"):
            await refresh_access_token(db, "old.refresh")


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------


class TestAuthRouter:
    def test_auth_routes_registered(self) -> None:
        paths = [r.path for r in app.routes]
        assert "/api/v1/auth/register" in paths
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/auth/me" in paths
        assert "/api/v1/auth/refresh" in paths
        assert "/api/v1/auth/logout" in paths
        assert "/api/v1/auth/password" in paths
        assert "/api/v1/auth/password-reset/request" in paths
        assert "/api/v1/auth/password-reset/confirm" in paths
