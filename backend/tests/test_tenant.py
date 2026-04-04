"""多租户数据隔离 (#19) 测试 — tenant.py 核心函数 + API 端点 org_id 注入。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.database import get_db as get_db_original
from app.core.deps import get_current_user
from app.core.tenant import (
    DEFAULT_QUOTA,
    _QUOTA_TABLE_MAP,
    check_quota,
    get_org_id,
    get_org_id_required,
)
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> MagicMock:
    """创建模拟用户对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "$2b$12$fake",
        "role": "user",
        "role_id": None,
        "org_id": uuid.uuid4(),
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


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """每个测试结束后清理 dependency_overrides。"""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# get_org_id / get_org_id_required 单元测试
# ---------------------------------------------------------------------------
    """get_org_id 依赖函数测试。"""

    @pytest.mark.asyncio
    async def test_returns_org_id_when_user_has_org(self):
        """有 org_id 的用户应返回 org_id。"""
        org = uuid.uuid4()
        user = _make_user(org_id=org)
        result = await get_org_id(user=user)
        assert result == org

    @pytest.mark.asyncio
    async def test_returns_none_when_user_has_no_org(self):
        """无 org_id 的用户（如 admin）应返回 None。"""
        user = _make_user(org_id=None, role="admin")
        result = await get_org_id(user=user)
        assert result is None


class TestGetOrgIdRequired:
    """get_org_id_required 依赖函数测试。"""

    @pytest.mark.asyncio
    async def test_returns_org_id_when_present(self):
        """有 org_id 的用户应正常返回。"""
        org = uuid.uuid4()
        user = _make_user(org_id=org)
        result = await get_org_id_required(user=user)
        assert result == org

    @pytest.mark.asyncio
    async def test_raises_403_for_normal_user_without_org(self):
        """普通用户无 org_id 应 403。"""
        user = _make_user(org_id=None, role="user")
        with pytest.raises(HTTPException) as exc_info:
            await get_org_id_required(user=user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "NO_ORG"

    @pytest.mark.asyncio
    async def test_raises_403_for_admin_without_org(self):
        """admin 无 org_id 也应 403（required 场景）。"""
        user = _make_user(org_id=None, role="admin")
        with pytest.raises(HTTPException) as exc_info:
            await get_org_id_required(user=user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# check_quota 单元测试
# ---------------------------------------------------------------------------


class TestCheckQuota:
    """check_quota 配额检查测试。"""

    @pytest.mark.asyncio
    async def test_skip_when_org_id_is_none(self):
        """org_id 为 None（admin 全局模式）时跳过检查。"""
        db = AsyncMock()
        # 不应执行任何数据库操作
        await check_quota(db, None, "max_agents")
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_resource_key_unknown(self):
        """未知的配额键应跳过检查。"""
        db = AsyncMock()
        await check_quota(db, uuid.uuid4(), "max_nonexistent_resource")
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_org_not_found(self):
        """组织不存在时跳过检查。"""
        db = AsyncMock()
        # 模拟组织查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        await check_quota(db, uuid.uuid4(), "max_agents")

    @pytest.mark.asyncio
    async def test_pass_when_under_quota(self):
        """在配额内应正常通过。"""
        db = AsyncMock()
        org_id = uuid.uuid4()

        # 第一次查询：组织配额
        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = {"max_agents": 10}

        # 第二次查询：当前数量
        count_result = MagicMock()
        count_result.scalar_one.return_value = 5

        db.execute.side_effect = [org_result, count_result]
        await check_quota(db, org_id, "max_agents")  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_raises_429_when_quota_exceeded(self):
        """超出配额应返回 429。"""
        db = AsyncMock()
        org_id = uuid.uuid4()

        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = {"max_agents": 5}

        count_result = MagicMock()
        count_result.scalar_one.return_value = 5

        db.execute.side_effect = [org_result, count_result]

        with pytest.raises(HTTPException) as exc_info:
            await check_quota(db, org_id, "max_agents")
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["code"] == "QUOTA_EXCEEDED"
        assert exc_info.value.detail["limit"] == 5
        assert exc_info.value.detail["current"] == 5

    @pytest.mark.asyncio
    async def test_uses_default_quota_when_org_has_empty_quota(self):
        """组织配额字典无对应键时使用默认值。"""
        db = AsyncMock()
        org_id = uuid.uuid4()

        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = {}  # 空配额 → 使用默认

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        db.execute.side_effect = [org_result, count_result]
        await check_quota(db, org_id, "max_agents")  # 默认50，当前0 → 通过

    @pytest.mark.asyncio
    async def test_raises_429_with_default_quota(self):
        """使用默认配额超出时也应 429。"""
        db = AsyncMock()
        org_id = uuid.uuid4()

        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = {}

        count_result = MagicMock()
        count_result.scalar_one.return_value = DEFAULT_QUOTA["max_agents"]

        db.execute.side_effect = [org_result, count_result]

        with pytest.raises(HTTPException) as exc_info:
            await check_quota(db, org_id, "max_agents")
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_skip_when_quota_limit_is_zero_or_negative(self):
        """配额值为 0 或负数时跳过检查（等同无限制）。"""
        db = AsyncMock()
        org_id = uuid.uuid4()

        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = {"max_agents": 0}
        db.execute.return_value = org_result

        await check_quota(db, org_id, "max_agents")  # 不应抛出


# ---------------------------------------------------------------------------
# 配额与映射表完整性
# ---------------------------------------------------------------------------


class TestQuotaConfig:
    """DEFAULT_QUOTA 与 _QUOTA_TABLE_MAP 配置一致性。"""

    def test_all_quota_keys_have_table_mapping(self):
        """所有默认配额键都必须有对应的表映射。"""
        for key in DEFAULT_QUOTA:
            assert key in _QUOTA_TABLE_MAP, f"配额键 {key} 缺少表映射"

    def test_all_table_mappings_have_default_quota(self):
        """所有表映射键都必须有默认配额值。"""
        for key in _QUOTA_TABLE_MAP:
            assert key in DEFAULT_QUOTA, f"表映射键 {key} 缺少默认配额"

    def test_default_quota_values_are_positive(self):
        """默认配额值必须为正整数。"""
        for key, val in DEFAULT_QUOTA.items():
            assert isinstance(val, int) and val > 0, f"{key}={val} 不是正整数"

    def test_quota_covers_all_resources(self):
        """配额应覆盖 11 种资源维度。"""
        expected = {
            "max_agents", "max_sessions", "max_teams", "max_workflows",
            "max_skills", "max_tool_groups", "max_guardrails", "max_mcp_servers",
            "max_memories", "max_im_channels", "max_scheduled_tasks",
        }
        assert set(DEFAULT_QUOTA.keys()) == expected


# ---------------------------------------------------------------------------
# API 端点 org_id 注入集成测试
# ---------------------------------------------------------------------------


def _make_agent_mock(**overrides) -> MagicMock:
    """创建模拟 AgentConfig 对象，用于 API 返回。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-agent",
        "description": "",
        "instructions": "test",
        "model": "gpt-4",
        "provider_name": None,
        "model_settings": None,
        "handoffs": [],
        "tools": [],
        "agent_tools": [],
        "tool_groups": [],
        "mcp_servers": [],
        "skills": [],
        "guardrails": {},
        "approval_mode": "suggest",
        "approval_config": None,
        "metadata_": {},
        "output_type": None,
        "provider_id": None,
        "org_id": None,
        "is_active": True,
        "created_by": None,
        "is_deleted": False,
        "deleted_at": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _override_deps(user: MagicMock, org_id: uuid.UUID | None = None) -> AsyncMock:
    """设置 FastAPI dependency overrides，返回 mock db session。"""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_original] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_org_id] = lambda: org_id if org_id is not None else user.org_id
    return mock_db


class TestAgentApiTenantIsolation:
    """Agent API 租户隔离测试。"""

    @patch("app.api.agents.agent_service")
    def test_list_agents_passes_org_id(self, mock_svc: MagicMock, client: TestClient):
        """list_agents 应将 org_id 传递给 service 层。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_svc.list_agents = AsyncMock(return_value=([], 0))

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        _, kwargs = mock_svc.list_agents.call_args
        assert kwargs.get("org_id") == org_id

    @patch("app.api.agents.agent_service")
    @patch("app.api.agents.check_quota", new_callable=AsyncMock)
    def test_create_agent_checks_quota(self, mock_quota: AsyncMock, mock_svc: MagicMock, client: TestClient):
        """create_agent 应调用 check_quota。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)

        now = datetime.now(timezone.utc)
        mock_agent = _make_agent_mock(name="test-agent", created_at=now, updated_at=now)
        mock_svc.create_agent = AsyncMock(return_value=mock_agent)

        resp = client.post("/api/v1/agents", json={"name": "test-agent", "model": "gpt-4", "instructions": "test"})
        assert resp.status_code == 201
        mock_quota.assert_called_once()
        args = mock_quota.call_args[0]
        assert args[1] == org_id
        assert args[2] == "max_agents"


class TestSessionApiTenantIsolation:
    """Session API 租户隔离测试。"""

    @patch("app.api.sessions.session_service")
    def test_list_sessions_passes_org_id(self, mock_svc: MagicMock, client: TestClient):
        """list_sessions 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_svc.list_sessions = AsyncMock(return_value=([], 0))

        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        _, kwargs = mock_svc.list_sessions.call_args
        assert kwargs.get("org_id") == org_id


class TestTeamApiTenantIsolation:
    """Team API 租户隔离测试。"""

    @patch("app.api.teams.team_service")
    def test_list_teams_passes_org_id(self, mock_svc: MagicMock, client: TestClient):
        """list_teams 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_svc.list_teams = AsyncMock(return_value=([], 0))

        resp = client.get("/api/v1/teams")
        assert resp.status_code == 200
        _, kwargs = mock_svc.list_teams.call_args
        assert kwargs.get("org_id") == org_id


class TestToolGroupApiTenantIsolation:
    """ToolGroup API 租户隔离测试。"""

    @patch("app.services.tool_group.list_tool_groups")
    def test_list_tool_groups_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_tool_groups 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/tool-groups")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestWorkflowApiTenantIsolation:
    """Workflow API 租户隔离测试。"""

    @patch("app.services.workflow.list_workflows")
    def test_list_workflows_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_workflows 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestMemoryApiTenantIsolation:
    """Memory API 租户隔离测试。"""

    @patch("app.services.memory.list_memories")
    def test_list_memories_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_memories 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/memories")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestScheduledTaskApiTenantIsolation:
    """ScheduledTask API 租户隔离测试。"""

    @patch("app.services.scheduled_task.list_scheduled_tasks")
    def test_list_tasks_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_tasks 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id, role="admin")
        _override_deps(user)
        # require_admin 需要 admin 角色
        from app.core.deps import require_admin
        app.dependency_overrides[require_admin] = lambda: user
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/scheduled-tasks")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestIMChannelApiTenantIsolation:
    """IMChannel API 租户隔离测试。"""

    @patch("app.services.im_channel.list_channels")
    def test_list_channels_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_channels 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id, role="admin")
        _override_deps(user)
        from app.core.deps import require_admin
        app.dependency_overrides[require_admin] = lambda: user
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/im-channels")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestSkillApiTenantIsolation:
    """Skill API 租户隔离测试。"""

    @patch("app.services.skill.list_skills")
    def test_list_skills_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_skills 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/skills")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


class TestGuardrailApiTenantIsolation:
    """Guardrail API 租户隔离测试。"""

    @patch("app.services.guardrail.list_guardrail_rules")
    def test_list_guardrails_passes_org_id(self, mock_list: AsyncMock, client: TestClient):
        """list_guardrail_rules 应传递 org_id。"""
        org_id = uuid.uuid4()
        user = _make_user(org_id=org_id)
        _override_deps(user)
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/guardrails")
        assert resp.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("org_id") == org_id


# ---------------------------------------------------------------------------
# Admin 全局访问（org_id=None）
# ---------------------------------------------------------------------------


class TestAdminGlobalAccess:
    """Admin 用户不绑定组织时 org_id=None，不做过滤也不检查配额。"""

    @patch("app.api.agents.agent_service")
    def test_admin_without_org_sees_all(self, mock_svc: MagicMock, client: TestClient):
        """admin 无 org_id 时 service 层收到 org_id=None → 不过滤。"""
        user = _make_user(org_id=None, role="admin")
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_org_id] = lambda: None
        mock_svc.list_agents = AsyncMock(return_value=([], 0))

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        _, kwargs = mock_svc.list_agents.call_args
        assert kwargs.get("org_id") is None

    @patch("app.api.agents.agent_service")
    @patch("app.api.agents.check_quota", new_callable=AsyncMock)
    def test_admin_create_skips_quota(self, mock_quota: AsyncMock, mock_svc: MagicMock, client: TestClient):
        """admin 无 org_id 创建资源时 check_quota 收到 None → 内部跳过。"""
        user = _make_user(org_id=None, role="admin")
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_org_id] = lambda: None

        now = datetime.now(timezone.utc)
        mock_agent = _make_agent_mock(name="new-agent", created_at=now, updated_at=now)
        mock_svc.create_agent = AsyncMock(return_value=mock_agent)

        resp = client.post("/api/v1/agents", json={"name": "new-agent", "model": "gpt-4", "instructions": "x"})
        assert resp.status_code == 201
        mock_quota.assert_called_once()
        assert mock_quota.call_args[0][1] is None
