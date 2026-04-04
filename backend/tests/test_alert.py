"""告警规则 & 告警事件测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.alert import AlertEvent, AlertRule
from app.schemas.alert import (
    VALID_METRICS,
    VALID_OPERATORS,
    VALID_SEVERITIES,
    AlertEventListResponse,
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdate,
)


# ============================================================================
# Model 单元测试
# ============================================================================


class TestAlertRuleModel:
    """AlertRule ORM 模型测试。"""

    def test_create_with_defaults(self) -> None:
        """默认字段值。"""
        rule = AlertRule(
            name="test-rule",
            metric="error_rate",
            operator=">",
            threshold=10.0,
        )
        assert rule.name == "test-rule"
        assert rule.metric == "error_rate"
        assert rule.operator == ">"
        assert rule.threshold == 10.0
        assert rule.agent_name is None
        assert rule.last_triggered_at is None

    def test_tablename(self) -> None:
        assert AlertRule.__tablename__ == "alert_rules"


class TestAlertEventModel:
    """AlertEvent ORM 模型测试。"""

    def test_create(self) -> None:
        rule_id = uuid.uuid4()
        event = AlertEvent(
            rule_id=rule_id,
            metric_value=15.5,
            threshold=10.0,
            severity="critical",
            message="Over threshold",
        )
        assert event.rule_id == rule_id
        assert event.metric_value == 15.5
        assert event.severity == "critical"

    def test_tablename(self) -> None:
        assert AlertEvent.__tablename__ == "alert_events"


# ============================================================================
# Schema 单元测试
# ============================================================================


class TestAlertRuleSchemas:
    """告警规则 Schema 验证测试。"""

    def test_create_valid(self) -> None:
        data = AlertRuleCreate(
            name="High Error Rate",
            metric="error_rate",
            operator=">",
            threshold=5.0,
        )
        assert data.name == "High Error Rate"
        assert data.window_minutes == 60
        assert data.cooldown_minutes == 30
        assert data.severity == "warning"

    def test_create_all_fields(self) -> None:
        data = AlertRuleCreate(
            name="Custom",
            metric="total_cost",
            operator=">=",
            threshold=100.0,
            window_minutes=120,
            agent_name="my-agent",
            severity="critical",
            cooldown_minutes=60,
            notification_config={"webhook_url": "https://example.com"},
        )
        assert data.agent_name == "my-agent"
        assert data.notification_config == {"webhook_url": "https://example.com"}

    def test_invalid_metric(self) -> None:
        with pytest.raises(ValueError, match="不支持的指标"):
            AlertRuleCreate(name="bad", metric="unknown", operator=">", threshold=1.0)

    def test_invalid_operator(self) -> None:
        with pytest.raises(ValueError, match="不支持的运算符"):
            AlertRuleCreate(name="bad", metric="error_rate", operator="!=", threshold=1.0)

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValueError, match="不支持的严重级别"):
            AlertRuleCreate(name="bad", metric="error_rate", operator=">", threshold=1.0, severity="fatal")

    def test_valid_metrics_set(self) -> None:
        assert "error_rate" in VALID_METRICS
        assert "avg_duration_ms" in VALID_METRICS
        assert "total_cost" in VALID_METRICS
        assert "total_tokens" in VALID_METRICS
        assert "trace_count" in VALID_METRICS

    def test_valid_operators_set(self) -> None:
        assert VALID_OPERATORS == {">", ">=", "<", "<=", "=="}

    def test_valid_severities_set(self) -> None:
        assert VALID_SEVERITIES == {"critical", "warning", "info"}

    def test_update_partial(self) -> None:
        data = AlertRuleUpdate(threshold=20.0, is_enabled=False)
        dump = data.model_dump(exclude_unset=True)
        assert dump == {"threshold": 20.0, "is_enabled": False}

    def test_update_validate_metric(self) -> None:
        with pytest.raises(ValueError):
            AlertRuleUpdate(metric="bad_metric")

    def test_response_from_attributes(self) -> None:
        now = datetime.now(timezone.utc)
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.name = "test"
        rule.description = ""
        rule.metric = "error_rate"
        rule.operator = ">"
        rule.threshold = 5.0
        rule.window_minutes = 60
        rule.agent_name = None
        rule.severity = "warning"
        rule.is_enabled = True
        rule.cooldown_minutes = 30
        rule.notification_config = {}
        rule.last_triggered_at = None
        rule.created_at = now
        rule.updated_at = now
        resp = AlertRuleResponse.model_validate(rule, from_attributes=True)
        assert resp.name == "test"

    def test_list_response(self) -> None:
        resp = AlertRuleListResponse(data=[], total=0)
        assert resp.total == 0

    def test_event_response(self) -> None:
        now = datetime.now(timezone.utc)
        event = MagicMock()
        event.id = uuid.uuid4()
        event.rule_id = uuid.uuid4()
        event.metric_value = 15.0
        event.threshold = 10.0
        event.severity = "critical"
        event.agent_name = None
        event.message = "alert"
        event.resolved_at = None
        event.created_at = now
        resp = AlertEventResponse.model_validate(event, from_attributes=True)
        assert resp.severity == "critical"


# ============================================================================
# Service 单元测试（Mock DB）
# ============================================================================


class TestAlertService:
    """告警服务单元测试。"""

    @pytest.mark.asyncio
    async def test_create_alert_rule(self) -> None:
        from app.services.alert import create_alert_rule

        db = AsyncMock()

        async def _refresh(obj: object) -> None:
            pass

        db.refresh = _refresh

        data = AlertRuleCreate(
            name="test", metric="error_rate", operator=">", threshold=5.0,
        )
        rule = await create_alert_rule(db, data)
        assert rule.name == "test"
        assert rule.metric == "error_rate"
        assert rule.org_id is None
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_alert_rule_with_org_id(self) -> None:
        """创建规则时传入 org_id 应直接设置到实例上。"""
        from app.services.alert import create_alert_rule

        db = AsyncMock()

        async def _refresh(obj: object) -> None:
            pass

        db.refresh = _refresh
        org = uuid.uuid4()

        data = AlertRuleCreate(
            name="test", metric="error_rate", operator=">", threshold=5.0,
        )
        rule = await create_alert_rule(db, data, org_id=org)
        assert rule.org_id == org

    @pytest.mark.asyncio
    async def test_evaluate_rule_not_triggered(self) -> None:
        """指标未超阈值时不触发。"""
        from app.services.alert import evaluate_rule

        db = AsyncMock()
        # _compute_metric 返回低于阈值的值
        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, idx: 2.0
        result_mock = MagicMock()
        result_mock.one_or_none.return_value = row_mock
        db.execute = AsyncMock(return_value=result_mock)

        rule = AlertRule(
            name="test",
            metric="error_rate",
            operator=">",
            threshold=5.0,
            window_minutes=60,
            cooldown_minutes=30,
            severity="warning",
        )
        rule.id = uuid.uuid4()
        rule.last_triggered_at = None
        rule.agent_name = None

        event = await evaluate_rule(db, rule)
        assert event is None

    @pytest.mark.asyncio
    async def test_evaluate_rule_triggered(self) -> None:
        """指标超阈值时触发告警。"""
        from app.services.alert import evaluate_rule

        db = AsyncMock()
        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, idx: 15.0
        result_mock = MagicMock()
        result_mock.one_or_none.return_value = row_mock
        db.execute = AsyncMock(return_value=result_mock)

        async def _refresh(obj: object) -> None:
            pass

        db.refresh = _refresh

        rule = AlertRule(
            name="High Error",
            metric="error_rate",
            operator=">",
            threshold=10.0,
            window_minutes=60,
            cooldown_minutes=30,
            severity="critical",
        )
        rule.id = uuid.uuid4()
        rule.last_triggered_at = None
        rule.agent_name = None

        event = await evaluate_rule(db, rule)
        assert event is not None
        assert event.severity == "critical"
        assert event.metric_value == 15.0
        db.add.assert_called()
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_evaluate_rule_cooldown(self) -> None:
        """冷却期内不触发。"""
        from app.services.alert import evaluate_rule

        db = AsyncMock()
        rule = AlertRule(
            name="test",
            metric="error_rate",
            operator=">",
            threshold=5.0,
            window_minutes=60,
            cooldown_minutes=30,
            severity="warning",
        )
        rule.id = uuid.uuid4()
        rule.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=5)  # 5 min ago, cooldown=30
        rule.agent_name = None

        event = await evaluate_rule(db, rule)
        assert event is None

    @pytest.mark.asyncio
    async def test_delete_soft(self) -> None:
        from app.services.alert import delete_alert_rule

        db = AsyncMock()
        rule = AlertRule(name="test", metric="error_rate", operator=">", threshold=5.0)
        rule.is_deleted = False
        rule.deleted_at = None

        await delete_alert_rule(db, rule)
        assert rule.is_deleted is True
        assert rule.deleted_at is not None
        db.commit.assert_awaited_once()


# ============================================================================
# API 路由测试（FastAPI TestClient）
# ============================================================================

from httpx import ASGITransport, AsyncClient

from app.core.database import get_db as get_db_original
from app.core.deps import get_current_user
from app.core.tenant import get_org_id
from app.main import create_app


def _make_app():
    """创建测试用 FastAPI 应用，覆盖认证 & 租户依赖。"""
    test_app = create_app()

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.role = "admin"
    mock_user.org_id = None

    test_app.dependency_overrides[get_current_user] = lambda: mock_user
    test_app.dependency_overrides[get_org_id] = lambda: None
    return test_app


class TestAlertAPI:
    """告警规则 API 端点测试。"""

    @pytest.mark.asyncio
    async def test_create_and_list(self) -> None:
        app = _make_app()

        mock_db = AsyncMock()
        created_rule = MagicMock()
        created_rule.id = uuid.uuid4()
        created_rule.name = "Test Rule"
        created_rule.description = ""
        created_rule.metric = "error_rate"
        created_rule.operator = ">"
        created_rule.threshold = 5.0
        created_rule.window_minutes = 60
        created_rule.agent_name = None
        created_rule.severity = "warning"
        created_rule.is_enabled = True
        created_rule.cooldown_minutes = 30
        created_rule.notification_config = {}
        created_rule.last_triggered_at = None
        created_rule.org_id = None
        created_rule.created_at = datetime.now(timezone.utc)
        created_rule.updated_at = datetime.now(timezone.utc)

        app.dependency_overrides[get_db_original] = lambda: mock_db

        with patch("app.services.alert.create_alert_rule", return_value=created_rule):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/alert-rules",
                    json={"name": "Test Rule", "metric": "error_rate", "operator": ">", "threshold": 5.0},
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["name"] == "Test Rule"
                assert data["metric"] == "error_rate"

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        with patch("app.services.alert.get_alert_rule", return_value=None):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/alert-rules/{uuid.uuid4()}")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_rule_success(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.name = "My Rule"
        rule.description = "desc"
        rule.metric = "total_cost"
        rule.operator = ">="
        rule.threshold = 100.0
        rule.window_minutes = 120
        rule.agent_name = "agent-a"
        rule.severity = "critical"
        rule.is_enabled = True
        rule.cooldown_minutes = 60
        rule.notification_config = {}
        rule.last_triggered_at = None
        rule.created_at = datetime.now(timezone.utc)
        rule.updated_at = datetime.now(timezone.utc)

        with patch("app.services.alert.get_alert_rule", return_value=rule):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/alert-rules/{rule.id}")
                assert resp.status_code == 200
                assert resp.json()["name"] == "My Rule"

    @pytest.mark.asyncio
    async def test_update_rule(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        now = datetime.now(timezone.utc)
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.name = "Updated"
        rule.description = ""
        rule.metric = "error_rate"
        rule.operator = ">"
        rule.threshold = 20.0
        rule.window_minutes = 60
        rule.agent_name = None
        rule.severity = "warning"
        rule.is_enabled = True
        rule.cooldown_minutes = 30
        rule.notification_config = {}
        rule.last_triggered_at = None
        rule.created_at = now
        rule.updated_at = now

        with (
            patch("app.services.alert.get_alert_rule", return_value=rule),
            patch("app.services.alert.update_alert_rule", return_value=rule),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.put(
                    f"/api/v1/alert-rules/{rule.id}",
                    json={"threshold": 20.0},
                )
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_rule(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        rule = MagicMock()
        rule.id = uuid.uuid4()

        with (
            patch("app.services.alert.get_alert_rule", return_value=rule),
            patch("app.services.alert.delete_alert_rule", return_value=None),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.delete(f"/api/v1/alert-rules/{rule.id}")
                assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_check_rule_not_triggered(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        rule = MagicMock()
        rule.id = uuid.uuid4()

        with (
            patch("app.services.alert.get_alert_rule", return_value=rule),
            patch("app.services.alert.evaluate_rule", return_value=None),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/v1/alert-rules/{rule.id}/check")
                assert resp.status_code == 200
                assert resp.json()["triggered"] is False

    @pytest.mark.asyncio
    async def test_check_rule_triggered(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        rule = MagicMock()
        rule.id = uuid.uuid4()

        event = MagicMock()
        event.id = uuid.uuid4()
        event.message = "告警触发"

        with (
            patch("app.services.alert.get_alert_rule", return_value=rule),
            patch("app.services.alert.evaluate_rule", return_value=event),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/v1/alert-rules/{rule.id}/check")
                assert resp.status_code == 200
                assert resp.json()["triggered"] is True

    @pytest.mark.asyncio
    async def test_list_events(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        rule = MagicMock()
        rule.id = uuid.uuid4()

        with (
            patch("app.services.alert.get_alert_rule", return_value=rule),
            patch("app.services.alert.list_alert_events", return_value=([], 0)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/alert-rules/{rule.id}/events")
                assert resp.status_code == 200
                assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_create_invalid_metric_422(self) -> None:
        app = _make_app()
        mock_db = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/alert-rules",
                json={"name": "bad", "metric": "not_exist", "operator": ">", "threshold": 1.0},
            )
            assert resp.status_code == 422
