"""认证 API 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_original
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.main import app
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> MagicMock:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "$2b$12$fake_hashed_password",
        "role": "user",
        "role_id": None,
        "is_active": True,
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

    def test_user_response_from_orm(self) -> None:
        user = _make_user()
        resp = UserResponse.model_validate(user, from_attributes=True)
        assert resp.username == "testuser"
        assert resp.email == "test@example.com"
        assert resp.role == "user"

    def test_register_email_normalized(self) -> None:
        data = UserRegister(username="alice", email="Alice@Test.COM", password="abcdef")
        assert data.email == "alice@test.com"


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
                mock_auth.return_value = "fake.jwt.token"
                resp = client.post("/api/v1/auth/login", json={
                    "username": "testuser",
                    "password": "secret123",
                })
                assert resp.status_code == 200
                body = resp.json()
                assert body["access_token"] == "fake.jwt.token"
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
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------


class TestAuthRouter:
    def test_auth_routes_registered(self) -> None:
        paths = [r.path for r in app.routes]
        assert "/api/v1/auth/register" in paths
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/auth/me" in paths
