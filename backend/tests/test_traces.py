"""Trace 持久化与查询 API 测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ═══════════════════════════════════════════════════════════════════
# Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


def _make_trace_record(**overrides: Any) -> MagicMock:
    """构造模拟 TraceRecord ORM 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": str(uuid.uuid4()),
        "workflow_name": "default",
        "group_id": None,
        "session_id": uuid.uuid4(),
        "agent_name": "test-agent",
        "status": "completed",
        "span_count": 3,
        "start_time": now,
        "end_time": now,
        "duration_ms": 150,
        "metadata": {},
        "metadata_": {},
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_span_record(**overrides: Any) -> MagicMock:
    """构造模拟 SpanRecord ORM 对象。"""
    now = datetime.now(UTC)
    trace_id = str(uuid.uuid4())
    defaults = {
        "id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "parent_span_id": None,
        "type": "agent",
        "name": "test-agent",
        "status": "completed",
        "start_time": now,
        "end_time": now,
        "duration_ms": 50,
        "input": {"text": "hello"},
        "input_data": {"text": "hello"},
        "output": {"text": "world"},
        "output_data": {"text": "world"},
        "metadata": {},
        "metadata_": {},
        "model": None,
        "token_usage": None,
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ═══════════════════════════════════════════════════════════════════
# Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestTraceSchemas:
    """Trace/Span Schema 验证。"""

    def test_trace_response_model_validate(self) -> None:
        """TraceResponse 从 ORM 对象正确构建。"""
        from app.schemas.trace import TraceResponse

        mock = _make_trace_record()
        resp = TraceResponse.model_validate(mock)
        assert resp.id == mock.id
        assert resp.workflow_name == "default"
        assert resp.agent_name == "test-agent"

    def test_span_response_model_validate(self) -> None:
        """SpanResponse 从 ORM 对象正确构建。"""
        from app.schemas.trace import SpanResponse

        mock = _make_span_record(model="gpt-4o", token_usage={"prompt_tokens": 10, "completion_tokens": 5})
        resp = SpanResponse.model_validate(mock)
        assert resp.id == mock.id
        assert resp.type == "agent"
        assert resp.token_usage == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_trace_list_response(self) -> None:
        """TraceListResponse 结构。"""
        from app.schemas.trace import TraceListResponse, TraceResponse

        items = [TraceResponse.model_validate(_make_trace_record()) for _ in range(3)]
        resp = TraceListResponse(data=items, total=10)
        assert len(resp.data) == 3
        assert resp.total == 10

    def test_trace_detail_response(self) -> None:
        """TraceDetailResponse 含 Trace + Spans。"""
        from app.schemas.trace import SpanResponse, TraceDetailResponse, TraceResponse

        trace = TraceResponse.model_validate(_make_trace_record())
        spans = [SpanResponse.model_validate(_make_span_record()) for _ in range(2)]
        resp = TraceDetailResponse(trace=trace, spans=spans)
        assert resp.trace.id == trace.id
        assert len(resp.spans) == 2


# ═══════════════════════════════════════════════════════════════════
# API 端点测试
# ═══════════════════════════════════════════════════════════════════


class TestTraceAPI:
    """Trace 查询 API 端点测试。"""

    @patch("app.api.traces.trace_service")
    def test_list_traces_empty(self, mock_svc: MagicMock) -> None:
        """空列表。"""
        mock_svc.list_traces = AsyncMock(return_value=([], 0))
        client = TestClient(app)
        resp = client.get("/api/v1/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    @patch("app.api.traces.trace_service")
    def test_list_traces_with_data(self, mock_svc: MagicMock) -> None:
        """列表含数据。"""
        traces = [_make_trace_record(agent_name=f"agent-{i}") for i in range(3)]
        mock_svc.list_traces = AsyncMock(return_value=(traces, 3))

        client = TestClient(app)
        resp = client.get("/api/v1/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        assert data["total"] == 3

    @patch("app.api.traces.trace_service")
    def test_list_traces_with_filters(self, mock_svc: MagicMock) -> None:
        """按 session_id 和 agent_name 筛选。"""
        sid = uuid.uuid4()
        mock_svc.list_traces = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get(f"/api/v1/traces?session_id={sid}&agent_name=my-agent")
        assert resp.status_code == 200
        # 验证参数传递
        call_kwargs = mock_svc.list_traces.call_args
        assert call_kwargs.kwargs["session_id"] == sid
        assert call_kwargs.kwargs["agent_name"] == "my-agent"

    @patch("app.api.traces.trace_service")
    def test_list_traces_pagination(self, mock_svc: MagicMock) -> None:
        """分页参数。"""
        mock_svc.list_traces = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces?limit=5&offset=10")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_traces.call_args
        assert call_kwargs.kwargs["limit"] == 5
        assert call_kwargs.kwargs["offset"] == 10

    @patch("app.api.traces.trace_service")
    def test_get_trace_detail(self, mock_svc: MagicMock) -> None:
        """获取 Trace 详情。"""
        trace_id = str(uuid.uuid4())
        trace = _make_trace_record(id=trace_id)
        spans = [
            _make_span_record(trace_id=trace_id, type="agent", name="root-agent"),
            _make_span_record(trace_id=trace_id, type="llm", name="gpt-4o", model="gpt-4o"),
            _make_span_record(trace_id=trace_id, type="tool", name="search"),
        ]
        mock_svc.get_trace_detail = AsyncMock(return_value=(trace, spans))

        client = TestClient(app)
        resp = client.get(f"/api/v1/traces/{trace_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace"]["id"] == trace_id
        assert len(data["spans"]) == 3
        assert data["spans"][0]["type"] == "agent"
        assert data["spans"][1]["type"] == "llm"
        assert data["spans"][2]["type"] == "tool"


# ═══════════════════════════════════════════════════════════════════
# 增强 API 测试
# ═══════════════════════════════════════════════════════════════════


class TestTraceAPIEnhanced:
    """Trace 增强查询 API 端点测试。"""

    @patch("app.api.traces.trace_service")
    def test_list_traces_status_filter(self, mock_svc: MagicMock) -> None:
        """按状态筛选。"""
        mock_svc.list_traces = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces?status=failed")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_traces.call_args
        assert call_kwargs.kwargs["status"] == "failed"

    @patch("app.api.traces.trace_service")
    def test_list_traces_duration_filter(self, mock_svc: MagicMock) -> None:
        """按耗时筛选。"""
        mock_svc.list_traces = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces?min_duration_ms=100&max_duration_ms=5000")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_traces.call_args
        assert call_kwargs.kwargs["min_duration_ms"] == 100
        assert call_kwargs.kwargs["max_duration_ms"] == 5000

    @patch("app.api.traces.trace_service")
    def test_list_traces_guardrail_triggered_filter(self, mock_svc: MagicMock) -> None:
        """按 Guardrail 触发筛选。"""
        mock_svc.list_traces = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces?has_guardrail_triggered=true")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_traces.call_args
        assert call_kwargs.kwargs["has_guardrail_triggered"] is True

    @patch("app.api.traces.trace_service")
    def test_get_trace_stats(self, mock_svc: MagicMock) -> None:
        """获取统计数据。"""
        mock_svc.get_trace_stats = AsyncMock(return_value={
            "total_traces": 50,
            "total_spans": 200,
            "avg_duration_ms": 320.5,
            "total_tokens": {
                "prompt_tokens": 5000,
                "completion_tokens": 2000,
                "total_tokens": 7000,
            },
            "span_type_counts": {
                "agent": 50,
                "llm": 80,
                "tool": 40,
                "handoff": 10,
                "guardrail": 20,
            },
            "guardrail_stats": {
                "total": 20,
                "triggered": 3,
                "trigger_rate": 0.15,
            },
            "error_rate": 0.02,
        })

        client = TestClient(app)
        resp = client.get("/api/v1/traces/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_traces"] == 50
        assert data["total_spans"] == 200
        assert data["avg_duration_ms"] == 320.5
        assert data["total_tokens"]["total_tokens"] == 7000
        assert data["span_type_counts"]["guardrail"] == 20
        assert data["guardrail_stats"]["triggered"] == 3
        assert data["guardrail_stats"]["trigger_rate"] == 0.15
        assert data["error_rate"] == 0.02

    @patch("app.api.traces.trace_service")
    def test_get_trace_stats_with_filters(self, mock_svc: MagicMock) -> None:
        """统计 API 参数传递。"""
        sid = uuid.uuid4()
        mock_svc.get_trace_stats = AsyncMock(return_value={
            "total_traces": 0, "total_spans": 0, "avg_duration_ms": None,
            "total_tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "span_type_counts": {"agent": 0, "llm": 0, "tool": 0, "handoff": 0, "guardrail": 0},
            "guardrail_stats": {"total": 0, "triggered": 0, "trigger_rate": 0.0},
            "error_rate": 0.0,
        })

        client = TestClient(app)
        resp = client.get(f"/api/v1/traces/stats?session_id={sid}&agent_name=my-agent")
        assert resp.status_code == 200
        call_kwargs = mock_svc.get_trace_stats.call_args
        assert call_kwargs.kwargs["session_id"] == sid
        assert call_kwargs.kwargs["agent_name"] == "my-agent"

    @patch("app.api.traces.trace_service")
    def test_list_spans(self, mock_svc: MagicMock) -> None:
        """搜索 Span 列表。"""
        spans = [_make_span_record(type="guardrail", name="pii_check", status="failed")]
        mock_svc.list_spans = AsyncMock(return_value=(spans, 1))

        client = TestClient(app)
        resp = client.get("/api/v1/traces/spans?type=guardrail&status=failed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["type"] == "guardrail"
        assert data["total"] == 1

    @patch("app.api.traces.trace_service")
    def test_list_spans_duration_filter(self, mock_svc: MagicMock) -> None:
        """按耗时搜索 Span。"""
        mock_svc.list_spans = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces/spans?min_duration_ms=500")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_spans.call_args
        assert call_kwargs.kwargs["min_duration_ms"] == 500

    @patch("app.api.traces.trace_service")
    def test_list_spans_name_search(self, mock_svc: MagicMock) -> None:
        """按名称模糊搜索 Span。"""
        mock_svc.list_spans = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/traces/spans?name=pii")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_spans.call_args
        assert call_kwargs.kwargs["name"] == "pii"


# ═══════════════════════════════════════════════════════════════════
# duration_ms 字段测试
# ═══════════════════════════════════════════════════════════════════


class TestDurationMs:
    """duration_ms 字段在响应中的正确性。"""

    def test_trace_response_has_duration_ms(self) -> None:
        """TraceResponse 含 duration_ms 字段。"""
        from app.schemas.trace import TraceResponse

        mock = _make_trace_record(duration_ms=250)
        resp = TraceResponse.model_validate(mock)
        assert resp.duration_ms == 250

    def test_span_response_has_duration_ms(self) -> None:
        """SpanResponse 含 duration_ms 字段。"""
        from app.schemas.trace import SpanResponse

        mock = _make_span_record(duration_ms=42)
        resp = SpanResponse.model_validate(mock)
        assert resp.duration_ms == 42

    def test_trace_response_duration_ms_nullable(self) -> None:
        """TraceResponse duration_ms 可为 None。"""
        from app.schemas.trace import TraceResponse

        mock = _make_trace_record(duration_ms=None)
        resp = TraceResponse.model_validate(mock)
        assert resp.duration_ms is None


# ═══════════════════════════════════════════════════════════════════
# Stats Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestStatsSchemas:
    """统计响应 Schema 验证。"""

    def test_trace_stats_response_defaults(self) -> None:
        """TraceStatsResponse 默认值。"""
        from app.schemas.trace import TraceStatsResponse

        resp = TraceStatsResponse()
        assert resp.total_traces == 0
        assert resp.total_spans == 0
        assert resp.avg_duration_ms is None
        assert resp.total_tokens.total_tokens == 0
        assert resp.guardrail_stats.trigger_rate == 0.0
        assert resp.error_rate == 0.0

    def test_trace_stats_response_full(self) -> None:
        """TraceStatsResponse 完整数据。"""
        from app.schemas.trace import TraceStatsResponse

        resp = TraceStatsResponse(
            total_traces=100,
            total_spans=500,
            avg_duration_ms=200.5,
            total_tokens={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
            span_type_counts={"agent": 100, "llm": 200, "tool": 100, "handoff": 50, "guardrail": 50},
            guardrail_stats={"total": 50, "triggered": 5, "trigger_rate": 0.1},
            error_rate=0.05,
        )
        assert resp.total_traces == 100
        assert resp.span_type_counts.llm == 200
        assert resp.guardrail_stats.triggered == 5

    def test_span_list_response(self) -> None:
        """SpanListResponse 结构。"""
        from app.schemas.trace import SpanListResponse, SpanResponse

        items = [SpanResponse.model_validate(_make_span_record()) for _ in range(2)]
        resp = SpanListResponse(data=items, total=5)
        assert len(resp.data) == 2
        assert resp.total == 5

    @patch("app.api.traces.trace_service")
    def test_get_trace_detail_not_found(self, mock_svc: MagicMock) -> None:
        """Trace 不存在返回 404。"""
        from app.core.exceptions import NotFoundError

        mock_svc.get_trace_detail = AsyncMock(side_effect=NotFoundError("Trace 不存在"))

        client = TestClient(app)
        resp = client.get("/api/v1/traces/non-existent")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# PostgresTraceProcessor 测试
# ═══════════════════════════════════════════════════════════════════


class TestPostgresTraceProcessor:
    """PostgresTraceProcessor 数据收集测试。"""

    @pytest.mark.asyncio
    async def test_collect_trace_and_spans(self) -> None:
        """收集完整 Trace + Span 数据。"""
        from app.services.trace_processor import PostgresTraceProcessor
        from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
        from ckyclaw_framework.tracing.trace import Trace

        processor = PostgresTraceProcessor(session_id="sess-123")

        trace = Trace(workflow_name="test-wf")
        agent_span = Span(
            trace_id=trace.trace_id,
            type=SpanType.AGENT,
            name="my-agent",
            status=SpanStatus.COMPLETED,
        )
        llm_span = Span(
            trace_id=trace.trace_id,
            parent_span_id=agent_span.span_id,
            type=SpanType.LLM,
            name="gpt-4o",
            model="gpt-4o",
            status=SpanStatus.COMPLETED,
            token_usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        )
        trace.spans = [agent_span, llm_span]

        # 模拟生命周期
        await processor.on_trace_start(trace)
        await processor.on_span_start(agent_span)
        await processor.on_span_end(agent_span)
        await processor.on_span_start(llm_span)
        await processor.on_span_end(llm_span)
        await processor.on_trace_end(trace)

        trace_data, span_data = processor.get_collected_data()

        assert trace_data is not None
        assert trace_data["id"] == trace.trace_id
        assert trace_data["workflow_name"] == "test-wf"
        assert trace_data["session_id"] == "sess-123"
        assert trace_data["agent_name"] == "my-agent"
        assert trace_data["span_count"] == 2

        assert len(span_data) == 2
        assert span_data[0]["type"] == "agent"
        assert span_data[1]["type"] == "llm"
        assert span_data[1]["model"] == "gpt-4o"
        assert span_data[1]["token_usage"]["total_tokens"] == 70

    @pytest.mark.asyncio
    async def test_empty_trace(self) -> None:
        """无 Span 的 Trace。"""
        from app.services.trace_processor import PostgresTraceProcessor
        from ckyclaw_framework.tracing.trace import Trace

        processor = PostgresTraceProcessor()

        trace = Trace()
        await processor.on_trace_start(trace)
        await processor.on_trace_end(trace)

        trace_data, span_data = processor.get_collected_data()
        assert trace_data is not None
        assert trace_data["span_count"] == 0
        assert span_data == []

    @pytest.mark.asyncio
    async def test_no_trace_started(self) -> None:
        """未调用 on_trace_start 时返回 None。"""
        from app.services.trace_processor import PostgresTraceProcessor

        processor = PostgresTraceProcessor()
        trace_data, span_data = processor.get_collected_data()
        assert trace_data is None
        assert span_data == []

    @pytest.mark.asyncio
    async def test_input_output_serialization(self) -> None:
        """Span input/output 安全序列化。"""
        from app.services.trace_processor import PostgresTraceProcessor
        from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
        from ckyclaw_framework.tracing.trace import Trace

        processor = PostgresTraceProcessor()
        trace = Trace()
        await processor.on_trace_start(trace)

        span = Span(
            trace_id=trace.trace_id,
            type=SpanType.TOOL,
            name="search",
            status=SpanStatus.COMPLETED,
            input="search query text",
            output={"results": ["a", "b"]},
        )
        await processor.on_span_end(span)

        _, span_data = processor.get_collected_data()
        assert span_data[0]["input_data"] == {"text": "search query text"}
        assert span_data[0]["output_data"] == {"results": ["a", "b"]}


# ═══════════════════════════════════════════════════════════════════
# 路由注册验证
# ═══════════════════════════════════════════════════════════════════


class TestTraceRouteRegistration:
    """验证 Trace 路由正确注册。"""

    def test_traces_routes_registered(self) -> None:
        """验证 /api/v1/traces 路由已注册。"""
        TestClient(app)
        routes = [r.path for r in app.routes]
        assert "/api/v1/traces" in routes
        assert "/api/v1/traces/{trace_id}" in routes
