"""ConsoleTraceProcessor 单元测试。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from ckyclaw_framework.tracing.console_processor import ConsoleTraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace


def _make_trace(trace_id: str = "t1", workflow_name: str = "test") -> Trace:
    """创建测试 Trace。"""
    t = Trace(workflow_name=workflow_name)
    t.trace_id = trace_id
    return t


def _make_span(
    span_id: str = "s1",
    name: str = "test_span",
    span_type: SpanType = SpanType.AGENT,
    status: SpanStatus = SpanStatus.COMPLETED,
) -> Span:
    """创建测试 Span。"""
    s = Span(type=span_type, name=name)
    s.span_id = span_id
    s.status = status
    return s


class TestConsoleTraceProcessorSpanEnd:
    """测试 on_span_end 覆盖 duration 和 token_info。"""

    @pytest.mark.asyncio
    async def test_span_end_with_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        """有 start_time 和 end_time 时输出 duration。"""
        proc = ConsoleTraceProcessor()
        span = _make_span("s1", "my_span")
        span.start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        span.end_time = datetime(2026, 1, 1, 0, 0, 1, 500000, tzinfo=UTC)  # 1.5 秒

        with caplog.at_level(logging.INFO):
            await proc.on_span_end(span)

        assert "duration=1500.0ms" in caplog.text

    @pytest.mark.asyncio
    async def test_span_end_with_token_usage(self, caplog: pytest.LogCaptureFixture) -> None:
        """有 token_usage 时输出 token 信息。"""
        proc = ConsoleTraceProcessor()
        span = _make_span("s2", "llm_span", SpanType.LLM)
        span.start_time = datetime(2026, 1, 1, tzinfo=UTC)
        span.end_time = datetime(2026, 1, 1, 0, 0, 0, 100000, tzinfo=UTC)
        span.token_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        with caplog.at_level(logging.INFO):
            await proc.on_span_end(span)

        assert "tokens=" in caplog.text
        assert "150" in caplog.text

    @pytest.mark.asyncio
    async def test_span_end_no_duration_no_tokens(self, caplog: pytest.LogCaptureFixture) -> None:
        """没有 start_time/end_time/token_usage 时不输出额外信息。"""
        proc = ConsoleTraceProcessor()
        span = _make_span("s3", "simple_span")
        # 不设置 start_time / end_time / token_usage

        with caplog.at_level(logging.INFO):
            await proc.on_span_end(span)

        assert "duration=" not in caplog.text
        assert "tokens=" not in caplog.text

    @pytest.mark.asyncio
    async def test_span_end_only_start_time(self, caplog: pytest.LogCaptureFixture) -> None:
        """只有 start_time 没有 end_time 时不输出 duration。"""
        proc = ConsoleTraceProcessor()
        span = _make_span()
        span.start_time = datetime(2026, 1, 1, tzinfo=UTC)
        span.end_time = None

        with caplog.at_level(logging.INFO):
            await proc.on_span_end(span)

        assert "duration=" not in caplog.text


class TestConsoleTraceProcessorTraceEnd:
    """测试 on_trace_end 覆盖 duration。"""

    @pytest.mark.asyncio
    async def test_trace_end_with_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        """Trace 有 start_time 和 end_time 时输出 duration。"""
        proc = ConsoleTraceProcessor()
        trace = _make_trace("t1", "workflow1")
        trace.start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        trace.end_time = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)
        trace.spans = []

        with caplog.at_level(logging.INFO):
            await proc.on_trace_end(trace)

        assert "duration=5000.0ms" in caplog.text

    @pytest.mark.asyncio
    async def test_trace_end_no_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        """无 start_time/end_time 时不输出 duration。"""
        proc = ConsoleTraceProcessor()
        trace = _make_trace("t2", "workflow2")
        trace.spans = []

        with caplog.at_level(logging.INFO):
            await proc.on_trace_end(trace)

        assert "duration=" not in caplog.text
        assert "[Trace End]" in caplog.text

    @pytest.mark.asyncio
    async def test_trace_end_span_count(self, caplog: pytest.LogCaptureFixture) -> None:
        """输出正确的 span 数量。"""
        proc = ConsoleTraceProcessor()
        trace = _make_trace()
        trace.spans = [_make_span("s1"), _make_span("s2"), _make_span("s3")]

        with caplog.at_level(logging.INFO):
            await proc.on_trace_end(trace)

        assert "spans=3" in caplog.text


class TestConsoleTraceProcessorStartEvents:
    """测试 start 事件输出。"""

    @pytest.mark.asyncio
    async def test_trace_start(self, caplog: pytest.LogCaptureFixture) -> None:
        proc = ConsoleTraceProcessor()
        trace = _make_trace("t1", "my_workflow")

        with caplog.at_level(logging.INFO):
            await proc.on_trace_start(trace)

        assert "[Trace Start]" in caplog.text
        assert "my_workflow" in caplog.text

    @pytest.mark.asyncio
    async def test_span_start(self, caplog: pytest.LogCaptureFixture) -> None:
        proc = ConsoleTraceProcessor()
        span = _make_span("s1", "agent_run", SpanType.AGENT)
        span.parent_span_id = "s_parent"

        with caplog.at_level(logging.INFO):
            await proc.on_span_start(span)

        assert "[Span Start]" in caplog.text
        assert "agent_run" in caplog.text
        assert "s_parent" in caplog.text
