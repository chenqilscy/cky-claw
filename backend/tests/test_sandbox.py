"""沙箱执行 API 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.database import get_db as get_db_original
from app.main import app
from app.schemas.sandbox import SandboxExecRequest, SandboxExecResponse


def _make_user(**overrides) -> MagicMock:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "username": "testuser",
        "email": "test@test.com",
        "hashed_password": "$2b$12$fake",
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


class TestSandboxSchemas:
    def test_request_valid(self) -> None:
        r = SandboxExecRequest(code='print("hello")')
        assert r.language == "python"
        assert r.timeout == 30

    def test_request_custom(self) -> None:
        r = SandboxExecRequest(code="x=1", language="python", timeout=10)
        assert r.timeout == 10

    def test_request_code_required(self) -> None:
        with pytest.raises(ValueError):
            SandboxExecRequest(code="")

    def test_response(self) -> None:
        r = SandboxExecResponse(exit_code=0, stdout="ok", stderr="", timed_out=False, duration_ms=100.0)
        assert r.exit_code == 0


class TestSandboxAPI:
    def test_execute_requires_auth(self, client: TestClient) -> None:
        from app.core.deps import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        resp = client.post("/api/v1/sandbox/execute", json={"code": "print(1)"})
        assert resp.status_code == 401

    def test_execute_success(self, client: TestClient) -> None:
        user = _make_user()
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.post(
                "/api/v1/sandbox/execute",
                json={"code": 'print("sandbox test")', "timeout": 10},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["exit_code"] == 0
            assert "sandbox test" in body["stdout"]
            assert body["timed_out"] is False
        finally:
            app.dependency_overrides.clear()

    def test_execute_syntax_error(self, client: TestClient) -> None:
        user = _make_user()
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.post(
                "/api/v1/sandbox/execute",
                json={"code": "def foo(", "timeout": 5},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["exit_code"] != 0
            assert "SyntaxError" in body["stderr"]
        finally:
            app.dependency_overrides.clear()

    def test_execute_timeout(self, client: TestClient) -> None:
        user = _make_user()
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.post(
                "/api/v1/sandbox/execute",
                json={"code": "import time; time.sleep(30)", "timeout": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["timed_out"] is True
        finally:
            app.dependency_overrides.clear()
