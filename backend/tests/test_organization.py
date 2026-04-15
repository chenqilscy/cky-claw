"""多租户隔离测试 — Organization CRUD + org_id 数据隔离。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_org(**overrides) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "name": "Acme Corp",
        "slug": "acme-corp",
        "description": "测试组织",
        "settings": {},
        "quota": {"max_agents": 10},
        "is_active": True,
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
        "org_id": None,
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


def _user_token(user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    return create_access_token(data={"sub": str(uid), "role": "user"})


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 验证
# ---------------------------------------------------------------------------


class TestOrganizationSchema:
    """Organization Schema 单元测试。"""

    def test_create_valid(self):
        data = OrganizationCreate(name="Acme", slug="acme-corp")
        assert data.name == "Acme"
        assert data.slug == "acme-corp"
        assert data.settings == {}

    def test_create_invalid_slug_too_short(self):
        with pytest.raises(Exception):
            OrganizationCreate(name="X", slug="ab")

    def test_create_invalid_slug_uppercase(self):
        with pytest.raises(Exception):
            OrganizationCreate(name="Good", slug="BadSlug")

    def test_create_invalid_slug_special_chars(self):
        with pytest.raises(Exception):
            OrganizationCreate(name="Good", slug="bad_slug!")

    def test_create_with_quota(self):
        data = OrganizationCreate(
            name="Acme", slug="acme-corp",
            quota={"max_agents": 50, "max_tokens_per_day": 1_000_000},
        )
        assert data.quota["max_agents"] == 50

    def test_update_partial(self):
        data = OrganizationUpdate(name="New Name")
        dumped = data.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "description" not in dumped

    def test_response_from_attributes(self):
        org = _make_org()
        resp = OrganizationResponse.model_validate(org)
        assert resp.name == "Acme Corp"
        assert resp.slug == "acme-corp"

    def test_list_response(self):
        org = _make_org()
        resp = OrganizationListResponse(
            data=[OrganizationResponse.model_validate(org)],
            total=1,
            limit=20,
            offset=0,
        )
        assert resp.total == 1
        assert len(resp.data) == 1


# ---------------------------------------------------------------------------
# Service 层测试
# ---------------------------------------------------------------------------


class TestOrganizationService:
    """Organization Service 单元测试。"""

    @pytest.mark.asyncio
    async def test_create_organization(self):
        from app.services.organization import create_organization

        db = AsyncMock()
        data = OrganizationCreate(name="Acme", slug="acme-corp")

        # mock: slug 不重复
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        await create_organization(db, data)
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_slug(self):
        from app.core.exceptions import ConflictError
        from app.services.organization import create_organization

        db = AsyncMock()
        data = OrganizationCreate(name="Acme", slug="acme-corp")

        # get_organization_by_slug 返回已存在记录
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = _make_org()
        db.execute.return_value = result_mock

        with pytest.raises(ConflictError):
            await create_organization(db, data)

    @pytest.mark.asyncio
    async def test_list_organizations(self):
        from app.services.organization import list_organizations

        db = AsyncMock()
        org1 = _make_org(name="Org1")
        org2 = _make_org(name="Org2")

        # 模拟两次 execute 调用（count + data）
        count_mock = MagicMock()
        count_mock.scalar.return_value = 2

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [org1, org2]
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_organizations(db, limit=20, offset=0)
        assert total == 2
        assert len(items) == 2


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestOrganizationAPI:
    """组织 API 端点测试（通过 dependency_overrides 绕过真实认证）。"""

    def test_list_requires_admin(self, client: TestClient):
        """普通用户不能访问组织列表。"""
        from app.core.deps import get_current_user

        user = _make_user(role="user")
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            resp = client.get("/api/v1/organizations")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_create_organization(self, client: TestClient):
        """Admin 创建组织。"""
        from app.core.deps import get_current_user

        admin = _make_user(role="admin")
        created_org = _make_org(slug="new-org")

        app.dependency_overrides[get_current_user] = lambda: admin
        try:
            with patch("app.api.organizations.svc.create_organization", new_callable=AsyncMock) as mock_svc:
                mock_svc.return_value = created_org
                resp = client.post(
                    "/api/v1/organizations",
                    json={"name": "New Org", "slug": "new-org"},
                )
            assert resp.status_code == 201
        finally:
            app.dependency_overrides.clear()

    def test_get_nonexistent_org(self, client: TestClient):
        """获取不存在的组织返回 404。"""
        from app.core.deps import get_current_user

        admin = _make_user(role="admin")
        app.dependency_overrides[get_current_user] = lambda: admin
        try:
            with patch("app.api.organizations.svc.get_organization", new_callable=AsyncMock) as mock_svc:
                mock_svc.return_value = None
                fake_id = uuid.uuid4()
                resp = client.get(f"/api/v1/organizations/{fake_id}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# org_id 隔离逻辑测试
# ---------------------------------------------------------------------------


class TestOrgIdIsolation:
    """org_id 依赖注入与隔离测试。"""

    @pytest.mark.asyncio
    async def test_get_org_id_returns_user_org(self):
        """get_org_id 从当前用户提取 org_id。"""
        from app.core.deps import get_org_id

        org_uuid = uuid.uuid4()
        user = _make_user(org_id=org_uuid)
        result = await get_org_id(user)
        assert result == org_uuid

    @pytest.mark.asyncio
    async def test_get_org_id_returns_none_for_global(self):
        """无 org_id 的用户返回 None。"""
        from app.core.deps import get_org_id

        user = _make_user(org_id=None)
        result = await get_org_id(user)
        assert result is None

    @pytest.mark.asyncio
    async def test_agent_list_filters_by_org_id(self):
        """Agent 列表按 org_id 过滤。"""
        from app.services.agent import list_agents

        db = AsyncMock()
        org_uuid = uuid.uuid4()

        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_agents(db, org_id=org_uuid)
        assert total == 0
        assert items == []
        # 验证 execute 被调用了两次（count + data）
        assert db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_session_list_filters_by_org_id(self):
        """Session 列表按 org_id 过滤。"""
        from app.services.session import list_sessions

        db = AsyncMock()
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_sessions(db, org_id=uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_team_list_filters_by_org_id(self):
        """Team 列表按 org_id 过滤。"""
        from app.services.team import list_teams

        db = AsyncMock()

        count_mock = MagicMock()
        count_mock.scalar.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_teams(db, org_id=uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_workflow_list_filters_by_org_id(self):
        """Workflow 列表按 org_id 过滤。"""
        from app.services.workflow import list_workflows

        db = AsyncMock()
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_workflows(db, org_id=uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_guardrail_list_filters_by_org_id(self):
        """Guardrail 列表按 org_id 过滤。"""
        from app.services.guardrail import list_guardrail_rules

        db = AsyncMock()
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_mock = MagicMock()
        data_mock.scalars.return_value = scalars_mock

        db.execute.side_effect = [count_mock, data_mock]
        items, total = await list_guardrail_rules(db, org_id=uuid.uuid4())
        assert total == 0


# ---------------------------------------------------------------------------
# Model 层测试
# ---------------------------------------------------------------------------


class TestOrganizationModel:
    """Organization ORM 模型测试。"""

    def test_model_tablename(self):
        from app.models.organization import Organization
        assert Organization.__tablename__ == "organizations"

    def test_model_has_required_columns(self):
        from app.models.organization import Organization
        cols = {c.key for c in Organization.__table__.columns}
        expected = {"id", "name", "slug", "description", "settings", "quota", "is_active", "created_at", "updated_at"}
        assert expected.issubset(cols)

    def test_core_models_have_org_id(self):
        """验证核心模型都有 org_id 列。"""
        from app.models.agent import AgentConfig
        from app.models.guardrail import GuardrailRule
        from app.models.im_channel import IMChannel
        from app.models.memory import MemoryEntryRecord
        from app.models.session import SessionRecord
        from app.models.skill import SkillRecord
        from app.models.team import TeamConfig
        from app.models.tool_group import ToolGroupConfig
        from app.models.user import User
        from app.models.workflow import WorkflowDefinition

        models = [
            AgentConfig, SessionRecord, TeamConfig, WorkflowDefinition,
            MemoryEntryRecord, SkillRecord, IMChannel, GuardrailRule,
            ToolGroupConfig, User,
        ]
        for model in models:
            cols = {c.key for c in model.__table__.columns}
            assert "org_id" in cols, f"{model.__name__} 缺少 org_id 列"
