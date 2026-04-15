"""数据导出 API 测试。"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.export import _sanitize_csv_cell
from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


def _make_token_usage_mock(**overrides) -> MagicMock:
    """构造模拟 TokenUsageLog 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "timestamp": now,
        "agent_name": "test-agent",
        "model": "deepseek-chat",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_cost": 0.001,
        "completion_cost": 0.002,
        "total_cost": 0.003,
        "session_id": uuid.uuid4(),
        "trace_id": str(uuid.uuid4()),
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_trace_mock(**overrides) -> MagicMock:
    """构造模拟 TraceRecord 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": str(uuid.uuid4()),
        "agent_name": "test-agent",
        "session_id": uuid.uuid4(),
        "status": "completed",
        "start_time": now,
        "end_time": now,
        "span_count": 5,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# _sanitize_csv_cell 测试
# ---------------------------------------------------------------------------

class TestSanitizeCsvCell:
    """CSV 注入防护函数测试。"""

    def test_normal_value(self) -> None:
        assert _sanitize_csv_cell("hello") == "hello"

    def test_none_value(self) -> None:
        assert _sanitize_csv_cell(None) == ""

    def test_empty_string(self) -> None:
        assert _sanitize_csv_cell("") == ""

    def test_equals_prefix(self) -> None:
        assert _sanitize_csv_cell("=cmd()") == "'=cmd()"

    def test_plus_prefix(self) -> None:
        assert _sanitize_csv_cell("+1234") == "'+1234"

    def test_minus_prefix(self) -> None:
        assert _sanitize_csv_cell("-payload") == "'-payload"

    def test_at_prefix(self) -> None:
        assert _sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_numeric_value(self) -> None:
        assert _sanitize_csv_cell(42) == "42"

    def test_uuid_value(self) -> None:
        uid = uuid.uuid4()
        assert _sanitize_csv_cell(str(uid)) == str(uid)


# ---------------------------------------------------------------------------
# Token Usage 导出 API 测试
# ---------------------------------------------------------------------------

class TestExportTokenUsage:
    """Token 用量 CSV 导出测试。"""

    @patch("app.services.token_usage.list_token_usage", new_callable=AsyncMock)
    def test_export_empty(self, mock_list: AsyncMock, client: TestClient) -> None:
        """无数据时返回仅含表头的 CSV。"""
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/export/token-usage")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1  # 仅表头
        assert "时间" in rows[0]
        assert "Total Tokens" in rows[0]

    @patch("app.services.token_usage.list_token_usage", new_callable=AsyncMock)
    def test_export_with_data(self, mock_list: AsyncMock, client: TestClient) -> None:
        """有数据时正确输出。"""
        rec = _make_token_usage_mock()
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/token-usage")
        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2  # 表头 + 1 数据行
        assert rows[1][1] == "test-agent"
        assert rows[1][2] == "deepseek-chat"

    @patch("app.services.token_usage.list_token_usage", new_callable=AsyncMock)
    def test_export_filters_passed(self, mock_list: AsyncMock, client: TestClient) -> None:
        """查询参数能正确传递到 service。"""
        mock_list.return_value = ([], 0)

        client.get("/api/v1/export/token-usage?agent_name=bot&model=gpt-4o")
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs.get("agent_name") == "bot"
        assert call_kwargs.kwargs.get("model") == "gpt-4o"
        assert call_kwargs.kwargs.get("limit") == 10000

    @patch("app.services.token_usage.list_token_usage", new_callable=AsyncMock)
    def test_export_csv_injection_protection(self, mock_list: AsyncMock, client: TestClient) -> None:
        """含危险前缀的 agent_name 被正确转义。"""
        rec = _make_token_usage_mock(agent_name="=cmd|'/C calc'!A0")
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/token-usage")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[1][1].startswith("'=")  # 单引号前缀

    @patch("app.services.token_usage.list_token_usage", new_callable=AsyncMock)
    def test_export_null_costs(self, mock_list: AsyncMock, client: TestClient) -> None:
        """cost 字段为 None 时输出 0。"""
        rec = _make_token_usage_mock(prompt_cost=None, completion_cost=None, total_cost=None)
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/token-usage")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[1][6] == "0"  # prompt_cost
        assert rows[1][7] == "0"  # completion_cost
        assert rows[1][8] == "0"  # total_cost


# ---------------------------------------------------------------------------
# Runs 导出 API 测试
# ---------------------------------------------------------------------------

class TestExportRuns:
    """运行记录 CSV 导出测试。"""

    @patch("app.services.trace.list_traces", new_callable=AsyncMock)
    def test_export_empty(self, mock_list: AsyncMock, client: TestClient) -> None:
        """无数据时返回仅含表头的 CSV。"""
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/export/runs")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1

    @patch("app.services.trace.list_traces", new_callable=AsyncMock)
    def test_export_with_data(self, mock_list: AsyncMock, client: TestClient) -> None:
        """有数据时正确输出。"""
        rec = _make_trace_mock()
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/runs")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1][1] == "test-agent"
        assert rows[1][3] == "completed"

    @patch("app.services.trace.list_traces", new_callable=AsyncMock)
    def test_export_duration_calc(self, mock_list: AsyncMock, client: TestClient) -> None:
        """耗时计算正确。"""
        from datetime import timedelta

        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(seconds=2, milliseconds=500)
        rec = _make_trace_mock(start_time=start, end_time=end)
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/runs")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[1][6] == "2500"  # 2500ms

    @patch("app.services.trace.list_traces", new_callable=AsyncMock)
    def test_export_null_end_time(self, mock_list: AsyncMock, client: TestClient) -> None:
        """end_time 为 None 时耗时为空。"""
        rec = _make_trace_mock(end_time=None)
        mock_list.return_value = ([rec], 1)

        resp = client.get("/api/v1/export/runs")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[1][6] == ""  # duration_ms 为空

    @patch("app.services.trace.list_traces", new_callable=AsyncMock)
    def test_export_filename(self, mock_list: AsyncMock, client: TestClient) -> None:
        """Content-Disposition 包含正确文件名前缀。"""
        mock_list.return_value = ([], 0)

        resp = client.get("/api/v1/export/runs")
        cd = resp.headers["content-disposition"]
        assert "runs_" in cd
        assert ".csv" in cd
