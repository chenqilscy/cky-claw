"""软删除统一 (O10) 测试。"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest

# ---------- Model tests ----------


class TestSoftDeleteMixin:
    """验证 SoftDeleteMixin 字段在所有 15 个模型上正确生效。"""

    def test_agent_config_has_soft_delete_fields(self) -> None:
        from app.models.agent import AgentConfig

        cols = {c.name for c in AgentConfig.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_provider_config_has_soft_delete_fields(self) -> None:
        from app.models.provider import ProviderConfig

        cols = {c.name for c in ProviderConfig.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_guardrail_rule_has_soft_delete_fields(self) -> None:
        from app.models.guardrail import GuardrailRule

        cols = {c.name for c in GuardrailRule.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_mcp_server_config_has_soft_delete_fields(self) -> None:
        from app.models.mcp_server import MCPServerConfig

        cols = {c.name for c in MCPServerConfig.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_memory_entry_has_soft_delete_fields(self) -> None:
        from app.models.memory import MemoryEntryRecord

        cols = {c.name for c in MemoryEntryRecord.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_agent_template_has_soft_delete_fields(self) -> None:
        from app.models.agent_template import AgentTemplate

        cols = {c.name for c in AgentTemplate.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_im_channel_has_soft_delete_fields(self) -> None:
        from app.models.im_channel import IMChannel

        cols = {c.name for c in IMChannel.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_organization_has_soft_delete_fields(self) -> None:
        from app.models.organization import Organization

        cols = {c.name for c in Organization.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_provider_model_has_soft_delete_fields(self) -> None:
        from app.models.provider_model import ProviderModel

        cols = {c.name for c in ProviderModel.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_session_record_has_soft_delete_fields(self) -> None:
        from app.models.session import SessionRecord

        cols = {c.name for c in SessionRecord.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_tool_group_config_has_soft_delete_fields(self) -> None:
        from app.models.tool_group import ToolGroupConfig

        cols = {c.name for c in ToolGroupConfig.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_team_config_has_soft_delete_fields(self) -> None:
        from app.models.team import TeamConfig

        cols = {c.name for c in TeamConfig.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_workflow_definition_has_soft_delete_fields(self) -> None:
        from app.models.workflow import WorkflowDefinition

        cols = {c.name for c in WorkflowDefinition.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_scheduled_task_has_soft_delete_fields(self) -> None:
        from app.models.scheduled_task import ScheduledTask

        cols = {c.name for c in ScheduledTask.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_skill_record_has_soft_delete_fields(self) -> None:
        from app.models.skill import SkillRecord

        cols = {c.name for c in SkillRecord.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols

    def test_default_is_deleted_false(self) -> None:
        """验证 is_deleted 列默认值为 False。"""
        from app.models.provider import ProviderConfig

        col = ProviderConfig.__table__.c.is_deleted
        assert col.server_default is not None
        assert str(col.server_default.arg) == "false"

    def test_deleted_at_nullable(self) -> None:
        """验证 deleted_at 列可为空。"""
        from app.models.provider import ProviderConfig

        col = ProviderConfig.__table__.c.deleted_at
        assert col.nullable is True


# ---------- Service delete behavior tests (mocked DB) ----------


class TestSoftDeleteBehavior:
    """验证服务层 delete 函数执行软删除而非硬删除。"""

    @pytest.mark.asyncio
    async def test_provider_soft_delete(self) -> None:
        """delete_provider 设置 is_deleted=True 而非 db.delete()。"""
        from app.services.provider import delete_provider

        fake_provider = mock.MagicMock()
        fake_provider.is_deleted = False
        fake_provider.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.provider.get_provider", return_value=fake_provider):
            await delete_provider(db, uuid.uuid4())

        assert fake_provider.is_deleted is True
        assert fake_provider.deleted_at is not None
        db.commit.assert_awaited_once()
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_guardrail_soft_delete(self) -> None:
        """delete_guardrail_rule 设置 is_deleted=True。"""
        from app.services.guardrail import delete_guardrail_rule

        fake_rule = mock.MagicMock()
        fake_rule.is_deleted = False
        fake_rule.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.guardrail.get_guardrail_rule", return_value=fake_rule):
            await delete_guardrail_rule(db, uuid.uuid4())

        assert fake_rule.is_deleted is True
        assert fake_rule.deleted_at is not None
        db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_mcp_server_soft_delete(self) -> None:
        """delete_mcp_server 设置 is_deleted=True。"""
        from app.services.mcp_server import delete_mcp_server

        fake_record = mock.MagicMock()
        fake_record.is_deleted = False
        fake_record.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.mcp_server.get_mcp_server", return_value=fake_record):
            await delete_mcp_server(db, uuid.uuid4())

        assert fake_record.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_template_soft_delete(self) -> None:
        """delete_template 设置 is_deleted=True（非内置模板）。"""
        from app.services.agent_template import delete_template

        fake_template = mock.MagicMock()
        fake_template.is_builtin = False
        fake_template.is_deleted = False
        fake_template.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.agent_template.get_template", return_value=fake_template):
            await delete_template(db, uuid.uuid4())

        assert fake_template.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_session_soft_delete(self) -> None:
        """delete_session 设置 is_deleted=True。"""
        from app.services.session import delete_session

        fake_session = mock.MagicMock()
        fake_session.is_deleted = False
        fake_session.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.session.get_session", return_value=fake_session):
            await delete_session(db, uuid.uuid4())

        assert fake_session.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tool_group_soft_delete(self) -> None:
        """delete_tool_group 设置 is_deleted=True。"""
        from app.services.tool_group import delete_tool_group

        fake_tg = mock.MagicMock()
        fake_tg.is_deleted = False
        fake_tg.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.tool_group.get_tool_group_by_name", return_value=fake_tg):
            await delete_tool_group(db, "test-group")

        assert fake_tg.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_team_soft_delete(self) -> None:
        """delete_team 设置 is_deleted=True。"""
        from app.services.team import delete_team

        fake_team = mock.MagicMock()
        fake_team.is_deleted = False
        fake_team.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.team.get_team", return_value=fake_team):
            await delete_team(db, uuid.uuid4())

        assert fake_team.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_workflow_soft_delete(self) -> None:
        """delete_workflow 设置 is_deleted=True。"""
        from app.services.workflow import delete_workflow

        fake_wf = mock.MagicMock()
        fake_wf.is_deleted = False
        fake_wf.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.workflow.get_workflow", return_value=fake_wf):
            await delete_workflow(db, uuid.uuid4())

        assert fake_wf.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skill_soft_delete(self) -> None:
        """delete_skill 设置 is_deleted=True。"""
        from app.services.skill import delete_skill

        fake_skill = mock.MagicMock()
        fake_skill.is_deleted = False
        fake_skill.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.skill.get_skill", return_value=fake_skill):
            await delete_skill(db, uuid.uuid4())

        assert fake_skill.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_organization_soft_delete(self) -> None:
        """delete_organization 设置 is_deleted=True。"""
        from app.services.organization import delete_organization

        fake_org = mock.MagicMock()
        fake_org.is_deleted = False
        fake_org.deleted_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.organization.get_organization", return_value=fake_org):
            result = await delete_organization(db, uuid.uuid4())

        assert result is True
        assert fake_org.is_deleted is True
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_soft_delete(self) -> None:
        """delete_agent 设置 is_deleted=True + is_active=False。"""
        from app.services.agent import delete_agent

        fake_agent = mock.MagicMock()
        fake_agent.is_active = True
        fake_agent.is_deleted = False
        fake_agent.deleted_at = None
        fake_agent.updated_at = None

        db = mock.AsyncMock()
        with mock.patch("app.services.agent.get_agent_by_name", return_value=fake_agent):
            await delete_agent(db, "test-agent")

        assert fake_agent.is_deleted is True
        assert fake_agent.is_active is False
        assert fake_agent.deleted_at is not None
        db.delete.assert_not_awaited()


# ---------- Migration tests ----------


class TestMigration0030:
    """验证迁移文件结构正确。"""

    def test_migration_metadata(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migration_0030",
            "alembic/versions/0030_soft_delete_unified.py",
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert mod.revision == "0030"
        assert mod.down_revision == "0029"

    def test_migration_covers_all_tables(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migration_0030",
            "alembic/versions/0030_soft_delete_unified.py",
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert len(mod._TABLES) == 15
        assert "agent_configs" in mod._TABLES
        assert "provider_configs" in mod._TABLES
        assert "sessions" in mod._TABLES
