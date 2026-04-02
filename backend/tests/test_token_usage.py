"""Token 审计 API 单元测试。

使用 mock 方式测试 service 层辅助函数、schema 校验和 API 路由。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.token_usage import TokenUsageLog
from app.schemas.token_usage import (
    TokenUsageListResponse,
    TokenUsageLogResponse,
    TokenUsageSummaryItem,
    TokenUsageSummaryResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_token_usage_log(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 TokenUsageLog ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "session_id": uuid.uuid4(),
        "user_id": None,
        "agent_name": "test-agent",
        "model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "timestamp": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestTokenUsageSchemas:
    """Pydantic Schema 校验。"""

    def test_log_response_from_mock(self) -> None:
        """TokenUsageLogResponse 能从 mock ORM 对象构建。"""
        mock = _make_token_usage_log()
        resp = TokenUsageLogResponse.model_validate(mock, from_attributes=True)
        assert resp.agent_name == "test-agent"
        assert resp.total_tokens == 150

    def test_summary_item(self) -> None:
        """TokenUsageSummaryItem 校验。"""
        item = TokenUsageSummaryItem(
            agent_name="bot",
            model="gpt-4o",
            total_prompt_tokens=1000,
            total_completion_tokens=500,
            total_tokens=1500,
            call_count=10,
        )
        assert item.call_count == 10

    def test_list_response(self) -> None:
        """TokenUsageListResponse 序列化。"""
        mock = _make_token_usage_log()
        log_resp = TokenUsageLogResponse.model_validate(mock, from_attributes=True)
        resp = TokenUsageListResponse(data=[log_resp], total=1, limit=20, offset=0)
        assert resp.total == 1
        assert len(resp.data) == 1


# ---------------------------------------------------------------------------
# Service 辅助函数测试
# ---------------------------------------------------------------------------


class TestSaveTokenUsageFromTrace:
    """_save_token_usage_from_trace 辅助函数。"""

    @pytest.mark.asyncio
    async def test_extract_llm_spans(self) -> None:
        """从 Trace 中提取 LLM Span 并写入。"""
        from app.services.session import _save_token_usage_from_trace

        # 构造 mock trace
        agent_span = MagicMock()
        agent_span.span_id = "span-agent-1"
        agent_span.type = "agent"
        agent_span.name = "my-agent"

        llm_span = MagicMock()
        llm_span.span_id = "span-llm-1"
        llm_span.type = "llm"
        llm_span.name = "gpt-4o"
        llm_span.model = "gpt-4o"
        llm_span.parent_span_id = "span-agent-1"
        llm_span.token_usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

        trace = MagicMock()
        trace.trace_id = "trace-1"
        trace.spans = [agent_span, llm_span]

        db = AsyncMock()
        session_id = uuid.uuid4()

        await _save_token_usage_from_trace(db, trace, session_id=session_id)

        # 验证 db.add_all 被调用
        db.add_all.assert_called_once()
        logs = db.add_all.call_args[0][0]
        assert len(logs) == 1
        assert isinstance(logs[0], TokenUsageLog)
        assert logs[0].agent_name == "my-agent"
        assert logs[0].model == "gpt-4o"
        assert logs[0].prompt_tokens == 100
        assert logs[0].total_tokens == 150
        assert logs[0].session_id == session_id
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_non_llm_spans(self) -> None:
        """非 LLM Span 不写入。"""
        from app.services.session import _save_token_usage_from_trace

        tool_span = MagicMock()
        tool_span.span_id = "span-tool-1"
        tool_span.type = "tool"
        tool_span.token_usage = None

        trace = MagicMock()
        trace.trace_id = "trace-1"
        trace.spans = [tool_span]

        db = AsyncMock()
        await _save_token_usage_from_trace(db, trace)

        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_llm_span_without_usage(self) -> None:
        """LLM Span 无 token_usage 时不写入。"""
        from app.services.session import _save_token_usage_from_trace

        llm_span = MagicMock()
        llm_span.span_id = "span-llm-1"
        llm_span.type = "llm"
        llm_span.token_usage = None

        trace = MagicMock()
        trace.trace_id = "trace-1"
        trace.spans = [llm_span]

        db = AsyncMock()
        await _save_token_usage_from_trace(db, trace)

        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_trace(self) -> None:
        """trace 为 None 时安全返回。"""
        from app.services.session import _save_token_usage_from_trace

        db = AsyncMock()
        await _save_token_usage_from_trace(db, None)
        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_llm_spans(self) -> None:
        """多个 LLM Span 全部提取。"""
        from app.services.session import _save_token_usage_from_trace

        agent_span = MagicMock()
        agent_span.span_id = "a1"
        agent_span.type = "agent"
        agent_span.name = "agent-1"

        llm1 = MagicMock()
        llm1.span_id = "l1"
        llm1.type = "llm"
        llm1.name = "gpt-4o"
        llm1.model = "gpt-4o"
        llm1.parent_span_id = "a1"
        llm1.token_usage = {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}

        llm2 = MagicMock()
        llm2.span_id = "l2"
        llm2.type = "llm"
        llm2.name = "gpt-4o"
        llm2.model = "gpt-4o"
        llm2.parent_span_id = "a1"
        llm2.token_usage = {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}

        trace = MagicMock()
        trace.trace_id = "trace-multi"
        trace.spans = [agent_span, llm1, llm2]

        db = AsyncMock()
        await _save_token_usage_from_trace(db, trace)

        logs = db.add_all.call_args[0][0]
        assert len(logs) == 2
        assert logs[0].total_tokens == 75
        assert logs[1].total_tokens == 120


# ---------------------------------------------------------------------------
# API 路由测试
# ---------------------------------------------------------------------------


class TestTokenUsageAPI:
    """Token 审计 API 路由测试。"""

    @patch("app.services.token_usage.list_token_usage")
    def test_list_empty(self, mock_list: AsyncMock, client: TestClient) -> None:
        """空列表返回。"""
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/token-usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["data"] == []

    @patch("app.services.token_usage.list_token_usage")
    def test_list_with_records(self, mock_list: AsyncMock, client: TestClient) -> None:
        """有记录的列表返回。"""
        mock = _make_token_usage_log()
        mock_list.return_value = ([mock], 1)
        resp = client.get("/api/v1/token-usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["agent_name"] == "test-agent"

    @patch("app.services.token_usage.list_token_usage")
    def test_list_with_filters(self, mock_list: AsyncMock, client: TestClient) -> None:
        """筛选参数传递。"""
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/token-usage?agent_name=bot&limit=5&offset=10")
        assert resp.status_code == 200
        # 验证参数传递
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["agent_name"] == "bot"
        assert call_kwargs["limit"] == 5
        assert call_kwargs["offset"] == 10

    @patch("app.services.token_usage.get_token_usage_summary")
    def test_summary_empty(self, mock_summary: AsyncMock, client: TestClient) -> None:
        """空汇总。"""
        mock_summary.return_value = []
        resp = client.get("/api/v1/token-usage/summary")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @patch("app.services.token_usage.get_token_usage_summary")
    def test_summary_with_data(self, mock_summary: AsyncMock, client: TestClient) -> None:
        """有数据的汇总。"""
        mock_summary.return_value = [
            TokenUsageSummaryItem(
                agent_name="bot",
                model="gpt-4o",
                total_prompt_tokens=1000,
                total_completion_tokens=500,
                total_tokens=1500,
                call_count=10,
            ),
        ]
        resp = client.get("/api/v1/token-usage/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["agent_name"] == "bot"
        assert data[0]["total_tokens"] == 1500
        assert data[0]["call_count"] == 10

    @patch("app.services.token_usage.get_token_usage_summary")
    def test_summary_with_filter(self, mock_summary: AsyncMock, client: TestClient) -> None:
        """汇总筛选参数传递。"""
        mock_summary.return_value = []
        resp = client.get("/api/v1/token-usage/summary?agent_name=bot")
        assert resp.status_code == 200
        call_kwargs = mock_summary.call_args[1]
        assert call_kwargs["agent_name"] == "bot"


# ---------------------------------------------------------------------------
# Model 测试
# ---------------------------------------------------------------------------


class TestTokenUsageLogModel:
    """TokenUsageLog SQLAlchemy 模型基础校验。"""

    def test_model_tablename(self) -> None:
        assert TokenUsageLog.__tablename__ == "token_usage_logs"

    def test_model_columns(self) -> None:
        """验证所有预期列存在。"""
        columns = {c.name for c in TokenUsageLog.__table__.columns}
        expected = {
            "id", "trace_id", "span_id", "session_id", "user_id",
            "agent_name", "model", "prompt_tokens", "completion_tokens",
            "total_tokens", "timestamp",
        }
        assert expected <= columns
