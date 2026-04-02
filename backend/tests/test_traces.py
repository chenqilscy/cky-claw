"""Trace 持久化与查询 API 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)
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
        "metadata": {},
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_span_record(**overrides: Any) -> MagicMock:
    """构造模拟 SpanRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
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
        "input": {"text": "hello"},
        "input_data": {"text": "hello"},
        "output": {"text": "world"},
        "output_data": {"text": "world"},
        "metadata": {},
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
        resp = TraceListResponse(items=items, total=10)
        assert len(resp.items) == 3
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
        assert data["items"] == []
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
        assert len(data["items"]) == 3
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
        from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
        from ckyclaw_framework.tracing.trace import Trace

        from app.services.trace_processor import PostgresTraceProcessor

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
        from ckyclaw_framework.tracing.trace import Trace

        from app.services.trace_processor import PostgresTraceProcessor

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
        from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
        from ckyclaw_framework.tracing.trace import Trace

        from app.services.trace_processor import PostgresTraceProcessor

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
        client = TestClient(app)
        routes = [r.path for r in app.routes]
        assert "/api/v1/traces" in routes
        assert "/api/v1/traces/{trace_id}" in routes
