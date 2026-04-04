"""APM 仪表盘 API 和服务层测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.apm import (
    AgentRankItem,
    ApmDashboardResponse,
    ApmOverview,
    DailyTrendItem,
    ModelUsageItem,
    ToolUsageItem,
)


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


def _mock_dashboard_response() -> ApmDashboardResponse:
    """构造完整 mock 响应。"""
    return ApmDashboardResponse(
        overview=ApmOverview(
            total_traces=150,
            total_spans=1200,
            total_tokens=50000,
            total_cost=1.25,
            avg_duration_ms=350.5,
            error_rate=2.5,
        ),
        agent_ranking=[
            AgentRankItem(
                agent_name="web-agent",
                call_count=80,
                total_tokens=30000,
                total_cost=0.75,
                avg_duration_ms=400.0,
                error_count=2,
            ),
        ],
        model_usage=[
            ModelUsageItem(
                model="gpt-4o",
                call_count=100,
                prompt_tokens=20000,
                completion_tokens=10000,
                total_tokens=30000,
                total_cost=0.9,
            ),
        ],
        daily_trend=[
            DailyTrendItem(date="2025-06-01", traces=10, tokens=5000, cost=0.1),
            DailyTrendItem(date="2025-06-02", traces=15, tokens=7000, cost=0.15),
        ],
        tool_usage=[
            ToolUsageItem(tool_name="web_search", call_count=50, avg_duration_ms=120.5),
        ],
    )


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestApmSchemas:
    """APM Schema 基本验证。"""

    def test_overview_defaults(self) -> None:
        """ApmOverview 默认值全零。"""
        o = ApmOverview()
        assert o.total_traces == 0
        assert o.total_spans == 0
        assert o.total_tokens == 0
        assert o.total_cost == 0.0
        assert o.avg_duration_ms == 0.0
        assert o.error_rate == 0.0

    def test_overview_custom_values(self) -> None:
        """ApmOverview 自定义值。"""
        o = ApmOverview(total_traces=100, error_rate=3.14)
        assert o.total_traces == 100
        assert o.error_rate == 3.14

    def test_agent_rank_item(self) -> None:
        """AgentRankItem 字段正确。"""
        item = AgentRankItem(agent_name="test-agent", call_count=42, total_tokens=1000)
        assert item.agent_name == "test-agent"
        assert item.call_count == 42
        assert item.total_cost == 0.0  # 默认值
        assert item.error_count == 0  # 默认值

    def test_model_usage_item(self) -> None:
        """ModelUsageItem 字段正确。"""
        item = ModelUsageItem(
            model="gpt-4o",
            call_count=50,
            prompt_tokens=10000,
            completion_tokens=5000,
            total_tokens=15000,
            total_cost=0.45,
        )
        assert item.model == "gpt-4o"
        assert item.prompt_tokens == 10000

    def test_daily_trend_item(self) -> None:
        """DailyTrendItem 字段正确。"""
        item = DailyTrendItem(date="2025-01-01", traces=10, tokens=500, cost=0.05)
        assert item.date == "2025-01-01"
        assert item.cost == 0.05

    def test_tool_usage_item(self) -> None:
        """ToolUsageItem 字段正确。"""
        item = ToolUsageItem(tool_name="web_search", call_count=100, avg_duration_ms=55.3)
        assert item.tool_name == "web_search"
        assert item.avg_duration_ms == 55.3

    def test_dashboard_response_structure(self) -> None:
        """ApmDashboardResponse 完整结构验证。"""
        resp = ApmDashboardResponse(
            overview=ApmOverview(),
            agent_ranking=[],
            model_usage=[],
            daily_trend=[],
            tool_usage=[],
        )
        assert resp.overview.total_traces == 0
        assert isinstance(resp.agent_ranking, list)
        assert isinstance(resp.tool_usage, list)

    def test_dashboard_serialization(self) -> None:
        """ApmDashboardResponse 序列化为 dict 正确。"""
        resp = _mock_dashboard_response()
        data = resp.model_dump()
        assert data["overview"]["total_traces"] == 150
        assert len(data["agent_ranking"]) == 1
        assert data["agent_ranking"][0]["agent_name"] == "web-agent"
        assert len(data["daily_trend"]) == 2


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestApmApi:
    """APM API 端点测试。"""

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_get_dashboard(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """获取 APM 仪表盘数据。"""
        mock_fn.return_value = _mock_dashboard_response()
        resp = client.get("/api/v1/apm/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["total_traces"] == 150
        assert data["overview"]["error_rate"] == 2.5
        assert len(data["agent_ranking"]) == 1
        assert data["agent_ranking"][0]["agent_name"] == "web-agent"
        assert len(data["model_usage"]) == 1
        assert len(data["daily_trend"]) == 2
        assert len(data["tool_usage"]) == 1

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_get_dashboard_default_days(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """默认 days=30。"""
        mock_fn.return_value = _mock_dashboard_response()
        client.get("/api/v1/apm/dashboard")
        mock_fn.assert_called_once()
        _, kwargs = mock_fn.call_args
        assert kwargs["days"] == 30

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_get_dashboard_custom_days(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """使用自定义天数参数。"""
        mock_fn.return_value = _mock_dashboard_response()
        resp = client.get("/api/v1/apm/dashboard?days=7")
        assert resp.status_code == 200
        _, kwargs = mock_fn.call_args
        assert kwargs["days"] == 7

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_get_dashboard_max_days(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """days=365 在允许范围内。"""
        mock_fn.return_value = _mock_dashboard_response()
        resp = client.get("/api/v1/apm/dashboard?days=365")
        assert resp.status_code == 200

    def test_get_dashboard_days_too_low(self, client: TestClient) -> None:
        """days=0 低于最小值返回 422。"""
        resp = client.get("/api/v1/apm/dashboard?days=0")
        assert resp.status_code == 422

    def test_get_dashboard_days_too_high(self, client: TestClient) -> None:
        """days=366 超出最大值返回 422。"""
        resp = client.get("/api/v1/apm/dashboard?days=366")
        assert resp.status_code == 422

    def test_get_dashboard_days_negative(self, client: TestClient) -> None:
        """days=-1 返回 422。"""
        resp = client.get("/api/v1/apm/dashboard?days=-1")
        assert resp.status_code == 422

    def test_get_dashboard_days_non_integer(self, client: TestClient) -> None:
        """days 非整数返回 422。"""
        resp = client.get("/api/v1/apm/dashboard?days=abc")
        assert resp.status_code == 422

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_get_dashboard_empty_data(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """空数据场景正常返回。"""
        mock_fn.return_value = ApmDashboardResponse(
            overview=ApmOverview(),
            agent_ranking=[],
            model_usage=[],
            daily_trend=[],
            tool_usage=[],
        )
        resp = client.get("/api/v1/apm/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["total_traces"] == 0
        assert data["overview"]["total_cost"] == 0.0
        assert data["agent_ranking"] == []
        assert data["model_usage"] == []
        assert data["daily_trend"] == []
        assert data["tool_usage"] == []

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_response_structure(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """响应包含所有必需字段。"""
        mock_fn.return_value = _mock_dashboard_response()
        resp = client.get("/api/v1/apm/dashboard")
        data = resp.json()
        # 顶层字段
        required_keys = {"overview", "agent_ranking", "model_usage", "daily_trend", "tool_usage"}
        assert required_keys == set(data.keys())
        # overview 字段
        overview_keys = {"total_traces", "total_spans", "total_tokens", "total_cost", "avg_duration_ms", "error_rate"}
        assert overview_keys == set(data["overview"].keys())
        # agent_ranking 字段
        rank_keys = {"agent_name", "call_count", "total_tokens", "total_cost", "avg_duration_ms", "error_count"}
        assert rank_keys == set(data["agent_ranking"][0].keys())
        # model_usage 字段
        model_keys = {"model", "call_count", "prompt_tokens", "completion_tokens", "total_tokens", "total_cost"}
        assert model_keys == set(data["model_usage"][0].keys())
        # daily_trend 字段
        trend_keys = {"date", "traces", "tokens", "cost"}
        assert trend_keys == set(data["daily_trend"][0].keys())
        # tool_usage 字段
        tool_keys = {"tool_name", "call_count", "avg_duration_ms"}
        assert tool_keys == set(data["tool_usage"][0].keys())

    @patch("app.api.apm.apm_service.get_apm_dashboard", new_callable=AsyncMock)
    def test_response_data_types(self, mock_fn: AsyncMock, client: TestClient) -> None:
        """响应值类型正确。"""
        mock_fn.return_value = _mock_dashboard_response()
        resp = client.get("/api/v1/apm/dashboard")
        data = resp.json()
        overview = data["overview"]
        assert isinstance(overview["total_traces"], int)
        assert isinstance(overview["total_cost"], float)
        assert isinstance(overview["error_rate"], float)
        rank = data["agent_ranking"][0]
        assert isinstance(rank["call_count"], int)
        assert isinstance(rank["total_cost"], float)
