"""Backend 覆盖率冲刺 Round 2 — 覆盖 APM 内部函数、scheduler_engine、
team、organization、alert 补充、agent_template 补充、mcp_server 补充、
trace_processor、token_usage 补充、workflow 补充、im_channel schema 等。

目标：将 backend 覆盖率从 90% → 95%+。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError

# ── helpers ──────────────────────────────────────────────────────────────

def _scalar_one(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar_one.return_value = val
    return r


def _scalar(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar.return_value = val
    return r


def _scalar_one_or_none(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar_one_or_none.return_value = val
    return r


def _scalars_all(vals: list):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalars.return_value.all.return_value = vals
    return r


def _rows(vals: list):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.all.return_value = vals
    return r


def _one(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.one.return_value = val
    return r


def _rowcount(n: int):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.rowcount = n
    return r


def _mock_db(*execute_results) -> AsyncMock:  # type: ignore[no-untyped-def]
    db = AsyncMock()
    if execute_results:
        db.execute = AsyncMock(side_effect=list(execute_results))
    else:
        db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.scalar = AsyncMock(return_value=None)
    return db


def _make_orm(**fields) -> MagicMock:  # type: ignore[no-untyped-def]
    obj = MagicMock()
    for k, v in fields.items():
        setattr(obj, k, v)
    return obj


# ═════════════════════════════════════════════════════════════════════════
# APM — 直接测试内部子函数 (37% → high%)
# ═════════════════════════════════════════════════════════════════════════


class TestAPMInternalFunctions:
    """直接测试 _get_overview / _get_agent_ranking / _get_model_usage / _get_daily_trend / _get_tool_usage。"""

    @pytest.mark.asyncio
    async def test_get_overview(self) -> None:
        from app.services.apm import _get_overview

        trace_row = MagicMock()
        trace_row.total_traces = 10
        trace_row.avg_duration_ms = 150.5
        trace_row.error_count = 2

        span_count = 20

        token_row = MagicMock()
        token_row.total_tokens = 5000
        token_row.total_cost = 0.5

        db = _mock_db(
            _one(trace_row),       # trace stats
            _scalar_one(span_count),  # span count
            _one(token_row),         # token stats
        )
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_overview(db, since)
        assert result.total_traces == 10
        assert result.total_spans == 20
        assert result.total_tokens == 5000
        assert result.error_rate == pytest.approx(20.0)

    @pytest.mark.asyncio
    async def test_get_overview_zero_traces(self) -> None:
        from app.services.apm import _get_overview

        trace_row = MagicMock()
        trace_row.total_traces = 0
        trace_row.avg_duration_ms = None
        trace_row.error_count = 0

        token_row = MagicMock()
        token_row.total_tokens = None
        token_row.total_cost = None

        db = _mock_db(
            _one(trace_row),
            _scalar_one(0),
            _one(token_row),
        )
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_overview(db, since)
        assert result.total_traces == 0
        assert result.error_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_agent_ranking(self) -> None:
        from app.services.apm import _get_agent_ranking

        agent_row = MagicMock()
        agent_row.agent_name = "agent1"
        agent_row.call_count = 5
        agent_row.avg_duration_ms = 120.0
        agent_row.error_count = 1

        token_row = MagicMock()
        token_row.agent_name = "agent1"
        token_row.total_tokens = 3000
        token_row.total_cost = 0.3

        db = _mock_db(
            _rows([agent_row]),     # agent ranking rows
            _rows([token_row]),     # token stats per agent
        )
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_agent_ranking(db, since)
        assert len(result) == 1
        assert result[0].agent_name == "agent1"
        assert result[0].total_tokens == 3000

    @pytest.mark.asyncio
    async def test_get_agent_ranking_empty(self) -> None:
        from app.services.apm import _get_agent_ranking

        db = _mock_db(_rows([]))
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_agent_ranking(db, since)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_model_usage(self) -> None:
        from app.services.apm import _get_model_usage

        row = MagicMock()
        row.model = "gpt-4o"
        row.call_count = 25
        row.prompt_tokens = 1000
        row.completion_tokens = 500
        row.total_tokens = 1500
        row.total_cost = 0.15

        db = _mock_db(_rows([row]))
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_model_usage(db, since)
        assert len(result) == 1
        assert result[0].model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_get_daily_trend(self) -> None:
        from app.services.apm import _get_daily_trend

        trace_row = MagicMock()
        trace_row.day = "2026-01-01"
        trace_row.traces = 10

        token_row = MagicMock()
        token_row.day = "2026-01-01"
        token_row.tokens = 5000
        token_row.cost = 0.5

        db = _mock_db(_rows([trace_row]), _rows([token_row]))
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_daily_trend(db, since)
        assert len(result) == 1
        assert result[0].traces == 10
        assert result[0].tokens == 5000

    @pytest.mark.asyncio
    async def test_get_tool_usage(self) -> None:
        from app.services.apm import _get_tool_usage

        row = MagicMock()
        row.name = "web_search"
        row.call_count = 20
        row.avg_duration_ms = 350.0

        db = _mock_db(_rows([row]))
        since = datetime.now(UTC) - timedelta(days=30)
        result = await _get_tool_usage(db, since)
        assert len(result) == 1
        assert result[0].tool_name == "web_search"


# ═════════════════════════════════════════════════════════════════════════
# Team Service 补充
# ═════════════════════════════════════════════════════════════════════════


class TestTeamServiceR2:
    """覆盖 team.py 未覆盖分支（create conflict + update 全路径）。"""

    @pytest.mark.asyncio
    async def test_create_team_conflict(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.team import TeamConfigCreate
        from app.services.team import create_team

        db = _mock_db()
        db.commit = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        data = TeamConfigCreate(name="team1", protocol="SEQUENTIAL")
        with pytest.raises(ConflictError):
            await create_team(db, data)
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_team(self) -> None:
        from app.schemas.team import TeamConfigUpdate
        from app.services.team import update_team

        mock_team = _make_orm(
            id=uuid.uuid4(), is_deleted=False, name="team1",
            protocol="ROUND_ROBIN", coordinator_agent_id=None,
        )
        db = _mock_db(_scalar_one_or_none(mock_team))
        data = TeamConfigUpdate(description="updated")
        await update_team(db, mock_team.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_team_not_found(self) -> None:
        from app.schemas.team import TeamConfigUpdate
        from app.services.team import update_team

        db = _mock_db(_scalar_one_or_none(None))
        data = TeamConfigUpdate(description="updated")
        with pytest.raises(NotFoundError):
            await update_team(db, uuid.uuid4(), data)


# ═════════════════════════════════════════════════════════════════════════
# Organization Service 补充
# ═════════════════════════════════════════════════════════════════════════


class TestOrganizationServiceR2:
    """覆盖 organization.py 未覆盖行。"""

    @pytest.mark.asyncio
    async def test_list_organizations_with_search(self) -> None:
        from app.services.organization import list_organizations

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_organizations(db, search="test")
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_organization_by_slug(self) -> None:
        from app.services.organization import get_organization_by_slug

        mock_org = _make_orm(slug="test-org")
        db = _mock_db(_scalar_one_or_none(mock_org))
        result = await get_organization_by_slug(db, "test-org")
        assert result is mock_org

    @pytest.mark.asyncio
    async def test_get_organization_by_slug_not_found(self) -> None:
        from app.services.organization import get_organization_by_slug

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_organization_by_slug(db, "notfound")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_organization(self) -> None:
        from app.schemas.organization import OrganizationUpdate
        from app.services.organization import update_organization

        mock_org = _make_orm(id=uuid.uuid4(), is_deleted=False, name="org1")
        db = _mock_db(_scalar_one_or_none(mock_org))
        data = OrganizationUpdate(name="org1-updated")
        await update_organization(db, mock_org.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_organization_not_found(self) -> None:
        from app.schemas.organization import OrganizationUpdate
        from app.services.organization import update_organization

        db = _mock_db(_scalar_one_or_none(None))
        data = OrganizationUpdate(name="org1-updated")
        with pytest.raises(NotFoundError):
            await update_organization(db, uuid.uuid4(), data)

    @pytest.mark.asyncio
    async def test_delete_organization(self) -> None:
        from app.services.organization import delete_organization

        mock_org = _make_orm(id=uuid.uuid4(), is_deleted=False, deleted_at=None)
        db = _mock_db(_scalar_one_or_none(mock_org))
        result = await delete_organization(db, mock_org.id)
        assert result is True
        assert mock_org.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_organization_not_found(self) -> None:
        from app.services.organization import delete_organization

        db = _mock_db(_scalar_one_or_none(None))
        result = await delete_organization(db, uuid.uuid4())
        assert result is False


# ═════════════════════════════════════════════════════════════════════════
# Alert Service 补充 — 过滤分支 + eval 边界
# ═════════════════════════════════════════════════════════════════════════


class TestAlertServiceR2:
    """覆盖 alert.py 的过滤分支、_compute_metric、evaluate_rule 冷却等路径。"""

    @pytest.mark.asyncio
    async def test_list_alert_rules_severity_filter(self) -> None:
        from app.services.alert import list_alert_rules

        db = _mock_db(_scalars_all([]))
        db.scalar = AsyncMock(return_value=0)
        rows, total = await list_alert_rules(db, severity="critical")
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_alert_rule_with_org_id(self) -> None:
        from app.services.alert import get_alert_rule

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_alert_rule(db, uuid.uuid4(), org_id=uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_alert_events_with_severity(self) -> None:
        from app.services.alert import list_alert_events

        db = _mock_db(_scalars_all([]))
        db.scalar = AsyncMock(return_value=0)
        rows, total = await list_alert_events(db, severity="warning")
        assert total == 0

    @pytest.mark.asyncio
    async def test_compute_metric(self) -> None:
        from app.services.alert import _compute_metric

        result_mock = MagicMock()
        result_mock.one_or_none.return_value = (0.05,)

        db = _mock_db()
        db.execute = AsyncMock(return_value=result_mock)
        result = await _compute_metric(db, "error_rate", 5, None)
        assert result == 0.05

    @pytest.mark.asyncio
    async def test_compute_metric_with_agent_name(self) -> None:
        from app.services.alert import _compute_metric

        result_mock = MagicMock()
        result_mock.one_or_none.return_value = (0.1,)

        db = _mock_db()
        db.execute = AsyncMock(return_value=result_mock)
        result = await _compute_metric(db, "error_rate", 5, "agent1")
        assert result == 0.1

    @pytest.mark.asyncio
    async def test_compute_metric_no_rows(self) -> None:
        from app.services.alert import _compute_metric

        result_mock = MagicMock()
        result_mock.one_or_none.return_value = None

        db = _mock_db()
        db.execute = AsyncMock(return_value=result_mock)
        result = await _compute_metric(db, "error_rate", 5, None)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_compute_metric_unknown_metric(self) -> None:
        from app.services.alert import _compute_metric

        db = _mock_db()
        result = await _compute_metric(db, "unknown_metric", 5, None)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_compute_metric_exception(self) -> None:
        from app.services.alert import _compute_metric

        db = _mock_db()
        db.execute = AsyncMock(side_effect=Exception("db error"))
        result = await _compute_metric(db, "error_rate", 5, None)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_rule_cooldown_active(self) -> None:
        from app.services.alert import evaluate_rule

        now = datetime.now(UTC)
        mock_rule = _make_orm(
            id=uuid.uuid4(), name="rule1", is_enabled=True,
            metric="error_rate", operator=">", threshold=0.1,
            window_minutes=5, cooldown_minutes=10,
            last_triggered_at=now - timedelta(minutes=5),
            agent_name=None, severity="warning",
            notification_channels=[],
        )
        db = _mock_db()
        result = await evaluate_rule(db, mock_rule)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_rule_triggers_alert(self) -> None:
        from app.services.alert import evaluate_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), name="high-error", is_enabled=True,
            metric="error_rate", operator=">", threshold=0.05,
            window_minutes=5, cooldown_minutes=10,
            last_triggered_at=None,
            agent_name="agent1", severity="critical",
            notification_channels=[],
        )
        db = _mock_db()
        with patch("app.services.alert._compute_metric", AsyncMock(return_value=0.2)):
            result = await evaluate_rule(db, mock_rule)
        assert result is not None
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_rule_no_trigger(self) -> None:
        from app.services.alert import evaluate_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), name="low-error", is_enabled=True,
            metric="error_rate", operator=">", threshold=0.5,
            window_minutes=5, cooldown_minutes=10,
            last_triggered_at=None,
            agent_name=None, severity="warning",
            notification_channels=[],
        )
        db = _mock_db()
        with patch("app.services.alert._compute_metric", AsyncMock(return_value=0.01)):
            result = await evaluate_rule(db, mock_rule)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_all_rules_mixed(self) -> None:
        from app.services.alert import evaluate_all_rules

        rule1 = _make_orm(
            id=uuid.uuid4(), name="r1", is_enabled=True,
            metric="error_rate", operator=">", threshold=0.05,
            window_minutes=5, cooldown_minutes=10,
            last_triggered_at=None,
            agent_name=None, severity="warning",
            notification_channels=[],
        )
        rule2 = _make_orm(
            id=uuid.uuid4(), name="r2", is_enabled=True,
            metric="avg_latency", operator=">", threshold=0.1,
            window_minutes=5, cooldown_minutes=10,
            last_triggered_at=None,
            agent_name=None, severity="critical",
            notification_channels=[],
        )
        db = _mock_db(_scalars_all([rule1, rule2]))
        with patch("app.services.alert._compute_metric", AsyncMock(return_value=0.2)):
            events = await evaluate_all_rules(db)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_evaluate_all_rules_exception_in_one(self) -> None:
        from app.services.alert import evaluate_all_rules

        rule1 = _make_orm(
            id=uuid.uuid4(), name="r1", is_enabled=True,
        )
        db = _mock_db(_scalars_all([rule1]))
        with patch("app.services.alert.evaluate_rule", AsyncMock(side_effect=Exception("err"))):
            events = await evaluate_all_rules(db)
        assert events == []


# ═════════════════════════════════════════════════════════════════════════
# Agent Template 补充
# ═════════════════════════════════════════════════════════════════════════


class TestAgentTemplateR2:
    """覆盖 agent_template.py 未覆盖分支。"""

    @pytest.mark.asyncio
    async def test_get_template_by_name_not_found(self) -> None:
        from app.services.agent_template import get_template_by_name

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_template_by_name(db, "nonexistent")

    @pytest.mark.asyncio
    async def test_list_templates_with_category(self) -> None:
        from app.services.agent_template import list_templates

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_templates(db, category="routing")
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_builtin_template_fails(self) -> None:
        from app.schemas.agent_template import AgentTemplateUpdate
        from app.services.agent_template import update_template

        mock_t = _make_orm(id=uuid.uuid4(), is_deleted=False, is_builtin=True)
        db = _mock_db(_scalar_one_or_none(mock_t))
        data = AgentTemplateUpdate(description="updated")
        with pytest.raises(ValueError, match="内置模板"):
            await update_template(db, mock_t.id, data)

    @pytest.mark.asyncio
    async def test_delete_builtin_template_fails(self) -> None:
        from app.services.agent_template import delete_template

        mock_t = _make_orm(id=uuid.uuid4(), is_deleted=False, is_builtin=True)
        db = _mock_db(_scalar_one_or_none(mock_t))
        with pytest.raises(ValueError, match="内置模板"):
            await delete_template(db, mock_t.id)

    @pytest.mark.asyncio
    async def test_seed_builtin_templates(self) -> None:
        from app.services.agent_template import seed_builtin_templates

        db = _mock_db()
        # 让所有名称查询返回 None（不存在）→ 会创建
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        count = await seed_builtin_templates(db)
        assert count > 0  # 至少 seed 了一些
        db.commit.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════
# MCP Server 补充
# ═════════════════════════════════════════════════════════════════════════


class TestMCPServerR2:
    """覆盖 mcp_server.py 的 test_mcp_connection + 边界路径。"""

    @pytest.mark.asyncio
    async def test_update_mcp_server_sets_transport(self) -> None:
        """验证 update 正常路径（有效 transport_type）。"""
        from app.schemas.mcp_server import MCPServerUpdate
        from app.services.mcp_server import update_mcp_server

        mock_s = _make_orm(
            id=uuid.uuid4(), is_deleted=False, auth_config=None,
            transport_type="stdio", name="s1",
        )
        db = _mock_db()
        data = MCPServerUpdate(transport_type="sse")
        with patch("app.services.mcp_server.get_mcp_server", AsyncMock(return_value=mock_s)):
            result = await update_mcp_server(db, mock_s.id, data)
        assert result.transport_type == "sse"

    def test_mcp_server_schema_rejects_invalid_transport(self) -> None:
        """Schema 层直接拒绝无效 transport_type。"""
        from pydantic import ValidationError as PydanticValidationError

        from app.schemas.mcp_server import MCPServerUpdate

        with pytest.raises(PydanticValidationError):
            MCPServerUpdate(transport_type="invalid_transport")

    @pytest.mark.asyncio
    async def test_test_mcp_connection_success(self) -> None:
        from app.services.mcp_server import test_mcp_connection

        mock_s = _make_orm(
            id=uuid.uuid4(), is_deleted=False, name="s1",
            transport_type="stdio", command="python",
            args=["-m", "server"], env={}, auth_config=None,
            url=None, headers={},
        )
        db = _mock_db(_scalar_one_or_none(mock_s))

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search tool"
        mock_tool.parameters_schema = {"type": "object"}

        async def fake_connect(stack, config):  # type: ignore[no-untyped-def]
            return [mock_tool]

        with patch("app.services.mcp_server.get_mcp_server", AsyncMock(return_value=mock_s)), \
             patch("ckyclaw_framework.mcp.connection.connect_and_discover", side_effect=fake_connect):
            result = await test_mcp_connection(db, mock_s.id)
        assert result["success"] is True
        assert len(result["tools"]) == 1

    @pytest.mark.asyncio
    async def test_test_mcp_connection_import_error(self) -> None:
        from app.services.mcp_server import test_mcp_connection

        mock_s = _make_orm(
            id=uuid.uuid4(), is_deleted=False, name="s2",
            transport_type="stdio", command="python",
            args=[], env={}, auth_config=None,
            url=None, headers={},
        )
        db = _mock_db(_scalar_one_or_none(mock_s))

        with patch("app.services.mcp_server.get_mcp_server", AsyncMock(return_value=mock_s)), \
             patch.dict("sys.modules", {"ckyclaw_framework.mcp.connection": None, "ckyclaw_framework.mcp.server": None}):
            # 让 import 存在但 connect_and_discover 抛出 ImportError
            result = await test_mcp_connection(db, mock_s.id)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_test_mcp_connection_failure(self) -> None:
        from app.services.mcp_server import test_mcp_connection

        mock_s = _make_orm(
            id=uuid.uuid4(), is_deleted=False, name="s3",
            transport_type="sse", command=None,
            args=[], env={}, auth_config=None,
            url="http://localhost:8080", headers={},
        )
        db = _mock_db(_scalar_one_or_none(mock_s))

        async def fake_connect_err(stack, config):  # type: ignore[no-untyped-def]
            raise Exception("timeout")

        with patch("app.services.mcp_server.get_mcp_server", AsyncMock(return_value=mock_s)), \
             patch("ckyclaw_framework.mcp.connection.connect_and_discover", side_effect=fake_connect_err):
            result = await test_mcp_connection(db, mock_s.id)
        assert result["success"] is False
        assert "timeout" in result.get("error", "")


# ═════════════════════════════════════════════════════════════════════════
# Trace Processor
# ═════════════════════════════════════════════════════════════════════════


class TestTraceProcessorR2:
    """覆盖 trace_processor.py（79% → 100%）。"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        from app.services.trace_processor import PostgresTraceProcessor

        proc = PostgresTraceProcessor(session_id="sess-001")

        # on_trace_start
        mock_trace_start = MagicMock()
        mock_trace_start.trace_id = "t1"
        mock_trace_start.workflow_name = "wf1"
        mock_trace_start.group_id = "g1"
        mock_trace_start.start_time = datetime.now(UTC)
        mock_trace_start.spans = []
        await proc.on_trace_start(mock_trace_start)

        # on_span_start (空实现)
        mock_span = MagicMock()
        mock_span.span_id = "s1"
        mock_span.trace_id = "t1"
        mock_span.parent_span_id = None
        mock_span.type = MagicMock(value="agent")
        mock_span.name = "my_agent"
        mock_span.input = {"query": "hello"}
        mock_span.output = {"response": "world"}
        mock_span.start_time = datetime.now(UTC)
        mock_span.end_time = datetime.now(UTC) + timedelta(seconds=1)
        mock_span.duration_ms = 1000
        mock_span.status = MagicMock(value="completed")
        mock_span.error = None
        mock_span.metadata = {}
        mock_span.model = "gpt-4o"
        mock_span.token_usage = None
        await proc.on_span_start(mock_span)

        # on_span_end
        await proc.on_span_end(mock_span)

        # on_trace_end
        mock_trace_end = MagicMock()
        mock_trace_end.trace_id = "t1"
        mock_trace_end.status = "completed"
        mock_trace_end.start_time = datetime.now(UTC)
        mock_trace_end.end_time = datetime.now(UTC) + timedelta(seconds=2)
        mock_trace_end.spans = [mock_span]
        mock_trace_end.metadata = {}
        await proc.on_trace_end(mock_trace_end)

        # get_collected_data
        trace_data, span_data = proc.get_collected_data()
        assert trace_data is not None
        assert trace_data["id"] == "t1"
        assert trace_data["agent_name"] == "my_agent"
        assert len(span_data) == 1
        assert span_data[0]["type"] == "agent"

    @pytest.mark.asyncio
    async def test_on_span_end_without_input_output(self) -> None:
        from app.services.trace_processor import PostgresTraceProcessor

        proc = PostgresTraceProcessor()
        mock_span = MagicMock()
        mock_span.span_id = "s2"
        mock_span.trace_id = "t2"
        mock_span.parent_span_id = "s1"
        mock_span.type = MagicMock(value="tool")
        mock_span.name = "web_search"
        mock_span.input = None
        mock_span.output = None
        mock_span.start_time = datetime.now(UTC)
        mock_span.end_time = datetime.now(UTC) + timedelta(milliseconds=500)
        mock_span.duration_ms = 500
        mock_span.status = MagicMock(value="completed")
        mock_span.error = None
        mock_span.metadata = None
        mock_span.model = None
        mock_span.token_usage = None
        await proc.on_span_end(mock_span)

        _, spans = proc.get_collected_data()
        assert len(spans) == 1
        assert spans[0]["input_data"] is None

    def test_safe_serialize_dict(self) -> None:
        from app.services.trace_processor import _safe_serialize

        result = _safe_serialize({"key": "value"})
        assert result == {"key": "value"}

    def test_safe_serialize_string(self) -> None:
        from app.services.trace_processor import _safe_serialize

        result = _safe_serialize("hello")
        assert result == {"text": "hello"}

    def test_safe_serialize_list(self) -> None:
        from app.services.trace_processor import _safe_serialize

        result = _safe_serialize(["a", "b"])
        assert result == {"items": ["a", "b"]}

    def test_safe_serialize_none(self) -> None:
        from app.services.trace_processor import _safe_serialize

        # None doesn't match dict/str/list so falls through to str() fallback
        result = _safe_serialize(None)
        assert result == {"value": "None"}

    def test_safe_serialize_pydantic_model(self) -> None:
        from pydantic import BaseModel

        from app.services.trace_processor import _safe_serialize

        class TinyModel(BaseModel):
            foo: str = "bar"

        result = _safe_serialize(TinyModel())
        assert result == {"foo": "bar"}

    def test_safe_serialize_fallback(self) -> None:
        from app.services.trace_processor import _safe_serialize

        result = _safe_serialize(42)
        assert result == {"value": "42"}


# ═════════════════════════════════════════════════════════════════════════
# Token Usage 补充
# ═════════════════════════════════════════════════════════════════════════


class TestTokenUsageR2:
    """覆盖 token_usage.py 未覆盖的过滤分支和 group_by 分支。"""

    @pytest.mark.asyncio
    async def test_create_empty_logs(self) -> None:
        from app.services.token_usage import create_token_usage_logs

        db = _mock_db()
        await create_token_usage_logs(db, [])
        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_token_usage_with_all_filters(self) -> None:
        from app.services.token_usage import list_token_usage

        db = _mock_db(_scalar_one(3), _scalars_all([_make_orm()]))
        rows, total = await list_token_usage(
            db,
            agent_name="a1",
            session_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            model="gpt-4o",
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC),
        )
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_token_usage_summary_by_user(self) -> None:
        from app.schemas.token_usage import SummaryGroupBy
        from app.services.token_usage import get_token_usage_summary

        row = MagicMock()
        row.user_id = str(uuid.uuid4())
        row.total_prompt_tokens = 1000
        row.total_completion_tokens = 500
        row.total_tokens = 1500
        row.total_prompt_cost = 0.1
        row.total_completion_cost = 0.05
        row.total_cost = 0.15
        row.call_count = 10

        db = _mock_db(_rows([row]))
        result = await get_token_usage_summary(db, group_by=SummaryGroupBy.user)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_token_usage_summary_by_model(self) -> None:
        from app.schemas.token_usage import SummaryGroupBy
        from app.services.token_usage import get_token_usage_summary

        row = MagicMock()
        row.model = "gpt-4o"
        row.total_prompt_tokens = 2000
        row.total_completion_tokens = 1000
        row.total_tokens = 3000
        row.total_prompt_cost = 0.2
        row.total_completion_cost = 0.1
        row.total_cost = 0.3
        row.call_count = 20

        db = _mock_db(_rows([row]))
        result = await get_token_usage_summary(db, group_by=SummaryGroupBy.model)
        assert len(result) == 1


# ═════════════════════════════════════════════════════════════════════════
# Workflow 补充
# ═════════════════════════════════════════════════════════════════════════


class TestWorkflowR2:
    """覆盖 workflow.py 未覆盖分支。"""

    @pytest.mark.asyncio
    async def test_create_workflow_conflict(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.workflow import WorkflowCreate
        from app.services.workflow import create_workflow

        db = _mock_db()
        db.commit = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        data = WorkflowCreate(name="wf1")
        with pytest.raises(ConflictError):
            await create_workflow(db, data)

    @pytest.mark.asyncio
    async def test_get_workflow_by_name(self) -> None:
        from app.services.workflow import get_workflow_by_name

        mock_wf = _make_orm(name="wf1")
        db = _mock_db(_scalar_one_or_none(mock_wf))
        result = await get_workflow_by_name(db, "wf1")
        assert result is mock_wf

    @pytest.mark.asyncio
    async def test_get_workflow_by_name_not_found(self) -> None:
        from app.services.workflow import get_workflow_by_name

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_workflow_by_name(db, "nonexistent")

    @pytest.mark.asyncio
    async def test_list_workflows_with_org_id(self) -> None:
        from app.services.workflow import list_workflows

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm()]))
        rows, total = await list_workflows(db, org_id=uuid.uuid4())
        assert total == 1

    def test_validate_workflow_empty_id(self) -> None:
        from app.services.workflow import validate_workflow_definition

        steps = [{"id": "", "name": "s1", "agent_name": "a1"}]
        errors = validate_workflow_definition(steps=steps, edges=[])
        assert any("空步骤" in e for e in errors)

    def test_validate_workflow_duplicate_id(self) -> None:
        from app.services.workflow import validate_workflow_definition

        steps = [
            {"id": "s1", "name": "step1", "agent_name": "a1"},
            {"id": "s1", "name": "step2", "agent_name": "a2"},
        ]
        errors = validate_workflow_definition(steps=steps, edges=[])
        assert any("重复" in e for e in errors)

    def test_validate_workflow_invalid_edge(self) -> None:
        from app.services.workflow import validate_workflow_definition

        steps = [{"id": "s1", "name": "step1", "agent_name": "a1"}]
        edges = [{"source_step_id": "s1", "target_step_id": "s2"}]
        errors = validate_workflow_definition(steps=steps, edges=edges)
        assert any("不存在" in e for e in errors)

    def test_validate_workflow_cycle(self) -> None:
        from app.services.workflow import validate_workflow_definition

        steps = [
            {"id": "s1", "name": "step1", "agent_name": "a1"},
            {"id": "s2", "name": "step2", "agent_name": "a2"},
        ]
        edges = [
            {"source_step_id": "s1", "target_step_id": "s2"},
            {"source_step_id": "s2", "target_step_id": "s1"},
        ]
        errors = validate_workflow_definition(steps=steps, edges=edges)
        assert any("循环" in e for e in errors)


# ═════════════════════════════════════════════════════════════════════════
# IM Channel Schema 补充
# ═════════════════════════════════════════════════════════════════════════


class TestIMChannelSchemaR2:
    """覆盖 schemas/im_channel.py 的验证器和脱敏函数。"""

    def test_mask_app_config(self) -> None:
        from app.schemas.im_channel import _mask_app_config

        config = {"token": "secret123", "name": "test", "api_key": "sk-xxx"}
        result = _mask_app_config(config)
        assert result["token"] == "***"
        assert result["name"] == "test"  # 非敏感字段不变
        assert result["api_key"] == "***"

    def test_create_invalid_channel_type(self) -> None:
        from app.schemas.im_channel import IMChannelCreate

        with pytest.raises(Exception):
            IMChannelCreate(
                name="ch1",
                channel_type="invalid_type",
            )

    def test_update_invalid_channel_type(self) -> None:
        from app.schemas.im_channel import IMChannelUpdate

        with pytest.raises(Exception):
            IMChannelUpdate(channel_type="invalid_type")

    def test_response_masks_secret(self) -> None:
        from app.schemas.im_channel import IMChannelResponse

        resp = IMChannelResponse(
            id=uuid.uuid4(),
            name="ch1",
            description="test channel",
            channel_type="webhook",
            webhook_url=None,
            is_enabled=True,
            notify_approvals=False,
            approval_recipient_id=None,
            webhook_secret="my_secret",
            app_config={"token": "secret123", "webhook_url": "http://test"},
            agent_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.webhook_secret == "***"
        assert resp.app_config["token"] == "***"


# ═════════════════════════════════════════════════════════════════════════
# Scheduler Engine 补充
# ═════════════════════════════════════════════════════════════════════════


class TestSchedulerEngineR2:
    """覆盖 scheduler_engine.py 未覆盖行。"""

    @pytest.mark.asyncio
    async def test_poll_and_execute_no_tasks(self) -> None:
        from app.services.scheduler_engine import poll_and_execute

        mock_session = _mock_db(_scalars_all([]))

        ctx_mock = AsyncMock()
        ctx_mock.__aenter__ = AsyncMock(return_value=mock_session)
        ctx_mock.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.scheduler_engine.async_session_factory", return_value=ctx_mock):
            result = await poll_and_execute()
        assert result == 0

    @pytest.mark.asyncio
    async def test_poll_and_execute_with_tasks(self) -> None:
        from app.services.scheduler_engine import poll_and_execute

        mock_task = _make_orm(
            id=uuid.uuid4(), name="task1",
            agent_id=uuid.uuid4(), cron_expr="*/5 * * * *",
            input_text="hello", is_enabled=True,
        )
        mock_session = _mock_db(_scalars_all([mock_task]))

        ctx_mock = AsyncMock()
        ctx_mock.__aenter__ = AsyncMock(return_value=mock_session)
        ctx_mock.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.scheduler_engine.async_session_factory", return_value=ctx_mock), \
             patch("app.services.scheduler_engine.execute_task", AsyncMock()):
            result = await poll_and_execute()
        assert result == 1

    @pytest.mark.asyncio
    async def test_poll_and_execute_task_exception(self) -> None:
        """任务执行异常时仍返回任务数。"""
        from app.services.scheduler_engine import poll_and_execute

        mock_task = _make_orm(
            id=uuid.uuid4(), name="task_err",
            agent_id=uuid.uuid4(), cron_expr="*/5 * * * *",
            input_text="hi", is_enabled=True,
        )
        mock_session = _mock_db(_scalars_all([mock_task]))

        ctx_mock = AsyncMock()
        ctx_mock.__aenter__ = AsyncMock(return_value=mock_session)
        ctx_mock.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.scheduler_engine.async_session_factory", return_value=ctx_mock), \
             patch("app.services.scheduler_engine.execute_task", AsyncMock(side_effect=Exception("fail"))):
            result = await poll_and_execute()
        assert result == 1  # 仍返回 1

    def test_start_and_stop_scheduler(self) -> None:
        import app.services.scheduler_engine as eng

        # 保存旧状态
        old_task = eng._scheduler_task

        try:
            # 模拟已有 task
            mock_task = MagicMock()
            mock_task.done.return_value = False
            eng._scheduler_task = mock_task

            eng.start_scheduler()  # 已运行，应 warning 返回
            assert eng._scheduler_task is mock_task

            eng.stop_scheduler()
            mock_task.cancel.assert_called_once()
            assert eng._scheduler_task is None
        finally:
            # 恢复
            eng._scheduler_task = old_task


# ═════════════════════════════════════════════════════════════════════════
# Role Service 补充
# ═════════════════════════════════════════════════════════════════════════


class TestRoleServiceR2:
    """覆盖 role.py 未覆盖分支。"""

    @pytest.mark.asyncio
    async def test_update_role_system_check(self) -> None:
        from app.schemas.role import RoleUpdate
        from app.services.role import update_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=True, description="sys")
        db = _mock_db(_scalar_one_or_none(mock_role))
        data = RoleUpdate(permissions={"agents": ["read"]})
        with pytest.raises(ValidationError, match="系统内置角色不允许修改权限"):
            await update_role(db, mock_role.id, data)

    @pytest.mark.asyncio
    async def test_update_role_description_only(self) -> None:
        from app.schemas.role import RoleUpdate
        from app.services.role import update_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=True, description="old")
        db = _mock_db(_scalar_one_or_none(mock_role))
        data = RoleUpdate(description="updated desc")
        result = await update_role(db, mock_role.id, data)
        assert result.description == "updated desc"

    @pytest.mark.asyncio
    async def test_delete_role_system_check(self) -> None:
        from app.services.role import delete_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=True)
        db = _mock_db(_scalar_one_or_none(mock_role))
        with pytest.raises(ValidationError, match="系统内置角色不允许删除"):
            await delete_role(db, mock_role.id)

    @pytest.mark.asyncio
    async def test_delete_role_with_users(self) -> None:
        from app.services.role import delete_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=False)
        db = _mock_db(
            _scalar_one_or_none(mock_role),  # find role
            _scalar(3),                       # user count
        )
        with pytest.raises(ValidationError, match="3 个用户"):
            await delete_role(db, mock_role.id)

    @pytest.mark.asyncio
    async def test_delete_role_success(self) -> None:
        from app.services.role import delete_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=False)
        db = _mock_db(
            _scalar_one_or_none(mock_role),  # find role
            _scalar(0),                       # no users
        )
        await delete_role(db, mock_role.id)
        db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_role_to_user_success(self) -> None:
        from app.services.role import assign_role_to_user

        mock_role = _make_orm(id=uuid.uuid4(), name="editor")
        mock_user = _make_orm(id=uuid.uuid4(), role_id=None, role="user")
        db = _mock_db(
            _scalar_one_or_none(mock_role),  # role lookup
            _scalar_one_or_none(mock_user),  # user lookup
        )
        await assign_role_to_user(db, mock_user.id, mock_role.id)
        assert mock_user.role_id == mock_role.id
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_role_role_not_found(self) -> None:
        from app.services.role import assign_role_to_user

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="角色"):
            await assign_role_to_user(db, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_assign_role_user_not_found(self) -> None:
        from app.services.role import assign_role_to_user

        mock_role = _make_orm(id=uuid.uuid4(), name="admin")
        db = _mock_db(
            _scalar_one_or_none(mock_role),   # role found
            _scalar_one_or_none(None),        # user not found
        )
        with pytest.raises(NotFoundError, match="用户"):
            await assign_role_to_user(db, uuid.uuid4(), mock_role.id)


# ═════════════════════════════════════════════════════════════════════════
# Guardrail Service 补充
# ═════════════════════════════════════════════════════════════════════════


class TestGuardrailR2:
    """覆盖 guardrail.py 的验证分支。"""

    @pytest.mark.asyncio
    async def test_create_guardrail_invalid_type(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="type 必须是"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="invalid_type", mode="regex",
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_invalid_mode(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="mode 必须是"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="input", mode="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_keyword_missing_keywords(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="keyword 模式必须提供 keywords 列表"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="input", mode="keyword",
                config={},  # missing keywords list
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_regex_invalid_pattern(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="无效的正则表达式"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="input", mode="regex",
                config={"patterns": ["["]},  # invalid regex
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_name_conflict(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db(_scalar_one_or_none(_make_orm(name="existing")))
        with pytest.raises(ConflictError):
            await create_guardrail_rule(
                db, name="existing", description="d",
                type_="input", mode="regex",
                config={"patterns": [".*"]},
            )


# ═════════════════════════════════════════════════════════════════════════
# Agent Locale 补充
# ═════════════════════════════════════════════════════════════════════════


class TestAgentLocaleR2:
    """覆盖 agent_locale.py 的 is_default 切换和 conflict 路径。"""

    @pytest.mark.asyncio
    async def test_create_locale_duplicate(self) -> None:
        from app.schemas.agent_locale import AgentLocaleCreate
        from app.services.agent_locale import create_locale

        aid = uuid.uuid4()
        db = _mock_db(
            _scalar_one_or_none(aid),         # _get_agent_id_by_name
            _scalar_one_or_none(uuid.uuid4()),  # exists check → duplicate found
        )
        data = AgentLocaleCreate(locale="en", instructions="test")
        with pytest.raises(ConflictError):
            await create_locale(db, "agent1", data)

    @pytest.mark.asyncio
    async def test_agent_not_found_for_locale(self) -> None:
        from app.schemas.agent_locale import AgentLocaleCreate
        from app.services.agent_locale import create_locale

        db = _mock_db(_scalar_one_or_none(None))
        data = AgentLocaleCreate(locale="en", instructions="test")
        with pytest.raises(NotFoundError):
            await create_locale(db, "nonexistent", data)

    @pytest.mark.asyncio
    async def test_delete_default_locale_fails(self) -> None:
        from app.services.agent_locale import delete_locale

        aid = uuid.uuid4()
        mock_locale = _make_orm(id=uuid.uuid4(), locale="en", agent_id=aid, is_default=True)
        db = _mock_db(
            _scalar_one_or_none(aid),
            _scalar_one_or_none(mock_locale),
        )
        with pytest.raises(ValidationError):
            await delete_locale(db, "agent1", "en")
