"""RBAC 角色权限测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.database import get_db as get_db_original
from app.main import app
from app.schemas.role import VALID_ACTIONS, VALID_RESOURCES, RoleCreate, RoleResponse, RoleUpdate, UserRoleAssign
from app.services.role import check_permission

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_role(**overrides) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-role",
        "description": "测试角色",
        "permissions": {"agents": ["read", "write"]},
        "is_system": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_user(**overrides) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "username": "admin",
        "email": "admin@test.com",
        "hashed_password": "$2b$12$fake",
        "role": "admin",
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


def _admin_token(user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    return create_access_token(data={"sub": str(uid), "role": "admin"})


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestRoleSchemas:
    def test_create_valid(self) -> None:
        data = RoleCreate(name="dev-team", permissions={"agents": ["read", "write"]})
        assert data.name == "dev-team"

    def test_create_invalid_name(self) -> None:
        with pytest.raises(ValueError):
            RoleCreate(name="ABC", permissions={})

    def test_create_invalid_resource(self) -> None:
        with pytest.raises(ValueError):
            RoleCreate(name="test-role", permissions={"invalid_resource": ["read"]})

    def test_create_invalid_action(self) -> None:
        with pytest.raises(ValueError):
            RoleCreate(name="test-role", permissions={"agents": ["hack"]})

    def test_update_permissions_validation(self) -> None:
        data = RoleUpdate(permissions={"agents": ["read"]})
        assert data.permissions is not None

    def test_update_invalid_resource(self) -> None:
        with pytest.raises(ValueError):
            RoleUpdate(permissions={"bad": ["read"]})

    def test_response_from_mock(self) -> None:
        role = _make_role()
        resp = RoleResponse.model_validate(role)
        assert resp.name == "test-role"

    def test_valid_resources_complete(self) -> None:
        assert "agents" in VALID_RESOURCES
        assert "roles" in VALID_RESOURCES
        assert "users" in VALID_RESOURCES

    def test_valid_actions_complete(self) -> None:
        assert {"read", "write", "delete", "execute"} == VALID_ACTIONS

    def test_user_role_assign(self) -> None:
        uid = uuid.uuid4()
        data = UserRoleAssign(role_id=uid)
        assert data.role_id == uid


# ---------------------------------------------------------------------------
# Service — check_permission
# ---------------------------------------------------------------------------


class TestCheckPermission:
    def test_has_permission(self) -> None:
        perms = {"agents": ["read", "write"], "providers": ["read"]}
        assert check_permission(perms, "agents", "read") is True
        assert check_permission(perms, "agents", "write") is True

    def test_no_permission(self) -> None:
        perms = {"agents": ["read"]}
        assert check_permission(perms, "agents", "delete") is False

    def test_no_resource(self) -> None:
        perms = {"agents": ["read"]}
        assert check_permission(perms, "providers", "read") is False

    def test_empty_permissions(self) -> None:
        assert check_permission({}, "agents", "read") is False


# ---------------------------------------------------------------------------
# Service 测试（模拟 DB）
# ---------------------------------------------------------------------------


class TestRoleService:
    @pytest.mark.asyncio
    async def test_create_role(self) -> None:
        from app.services.role import create_role

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        data = RoleCreate(name="my-role", permissions={"agents": ["read"]})
        await create_role(db, data)
        assert db.add.called

    @pytest.mark.asyncio
    async def test_list_roles(self) -> None:
        from app.services.role import list_roles

        mock_role = _make_role()
        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mock_role]
        execute_mock = MagicMock()
        execute_mock.scalar.return_value = 1
        execute_mock.scalars.return_value = scalars_mock
        db.execute = AsyncMock(return_value=execute_mock)

        roles, total = await list_roles(db)
        assert total == 1

    @pytest.mark.asyncio
    async def test_seed_system_roles_idempotent(self) -> None:
        from app.services.role import seed_system_roles

        db = AsyncMock()
        # 模拟所有角色已存在
        existing_role = _make_role(is_system=True)
        execute_mock = MagicMock()
        execute_mock.scalar_one_or_none.return_value = existing_role
        db.execute = AsyncMock(return_value=execute_mock)
        db.commit = AsyncMock()

        await seed_system_roles(db)
        # 不应该 add 新角色
        assert not db.add.called


# ---------------------------------------------------------------------------
# API 测试
# ---------------------------------------------------------------------------


class TestRoleAPI:
    def test_list_roles_requires_admin(self, client: TestClient) -> None:
        """普通 user 不能访问角色列表。"""
        from app.core.deps import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        user = _make_user(role="user")
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        # get_current_user 需要查询用户
        execute_mock = MagicMock()
        execute_mock.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.get(
                "/api/v1/roles",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_list_roles_success(self, client: TestClient) -> None:
        """Admin 可以列出角色。"""
        from app.core.deps import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        user = _make_user()
        token = _admin_token(user.id)
        mock_role = _make_role()

        mock_db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mock_role]
        execute_results = [
            # get_current_user: select User
            MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
            # count
            MagicMock(scalar=MagicMock(return_value=1)),
            # select roles
            MagicMock(scalars=MagicMock(return_value=scalars_mock)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.get(
                "/api/v1/roles",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert len(body["data"]) == 1
        finally:
            app.dependency_overrides.clear()

    def test_create_role_success(self, client: TestClient) -> None:
        """Admin 创建角色。"""
        user = _make_user()
        token = _admin_token(user.id)
        new_role = _make_role(name="new-role")

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        # refresh 需要给 role 对象填充属性
        async def _refresh(obj: object) -> None:
            for attr in ("id", "name", "description", "permissions", "is_system", "created_at", "updated_at"):
                setattr(obj, attr, getattr(new_role, attr))

        mock_db.refresh = AsyncMock(side_effect=_refresh)
        # get_current_user
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.post(
                "/api/v1/roles",
                json={"name": "new-role", "permissions": {"agents": ["read"]}},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201
        finally:
            app.dependency_overrides.clear()

    def test_delete_role_requires_admin(self, client: TestClient) -> None:
        """User 不能删除角色。"""
        from app.core.deps import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        user = _make_user(role="user")
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        async def _get_db():
            yield mock_db

        app.dependency_overrides[get_db_original] = _get_db
        try:
            resp = client.delete(
                f"/api/v1/roles/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# require_permission 依赖测试
# ---------------------------------------------------------------------------


class TestRequirePermission:
    def test_admin_fallback_has_all(self, client: TestClient) -> None:
        """当 user.role_id 为空时，admin 回退拥有全部权限。"""
        from app.core.deps import require_permission

        user = _make_user(role="admin", role_id=None)
        token = _admin_token(user.id)

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        # 创建一个测试端点
        from fastapi import APIRouter, Depends, FastAPI
        test_app = FastAPI()
        test_router = APIRouter()

        @test_router.get("/test-perm")
        async def _test_ep(_u: object = Depends(require_permission("agents", "write"))):
            return {"ok": True}

        test_app.include_router(test_router)

        # 替换 get_db
        from app.core.database import get_db

        async def _get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = _get_db
        test_client = TestClient(test_app)
        resp = test_client.get("/test-perm", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_user_fallback_read_only(self, client: TestClient) -> None:
        """当 user.role_id 为空时，普通 user 回退只有 read 权限。"""
        from app.core.deps import require_permission

        user = _make_user(role="user", role_id=None)
        token = create_access_token(data={"sub": str(user.id), "role": "user"})

        mock_db = AsyncMock()
        execute_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        mock_db.execute = AsyncMock(return_value=execute_mock)

        from fastapi import APIRouter, Depends, FastAPI
        test_app = FastAPI()
        test_router = APIRouter()

        @test_router.get("/test-perm-write")
        async def _test_ep(_u: object = Depends(require_permission("agents", "write"))):
            return {"ok": True}

        @test_router.get("/test-perm-read")
        async def _test_ep2(_u: object = Depends(require_permission("agents", "read"))):
            return {"ok": True}

        test_app.include_router(test_router)

        from app.core.database import get_db

        async def _get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = _get_db
        test_client = TestClient(test_app)

        # write should fail
        resp = test_client.get("/test-perm-write", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

        # read should pass
        resp = test_client.get("/test-perm-read", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
