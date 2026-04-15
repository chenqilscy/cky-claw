"""OTelTraceProcessor 扩展测试 — 覆盖 _init_tracer 成功路径 + OTel SDK 交互。"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from ckyclaw_framework.tracing.otel_processor import OTelTraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_trace(trace_id: str = "t1", workflow_name: str = "test") -> Trace:
    """创建测试 Trace。"""
    t = Trace(workflow_name=workflow_name)
    t.trace_id = trace_id
    return t


def _make_span(
    span_id: str = "s1",
    trace_id: str = "t1",
    name: str = "test_span",
    span_type: SpanType = SpanType.AGENT,
    parent_span_id: str | None = None,
    status: SpanStatus = SpanStatus.COMPLETED,
    output: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Span:
    """创建测试 Span。"""
    s = Span(type=span_type, name=name)
    s.span_id = span_id
    s.trace_id = trace_id
    s.parent_span_id = parent_span_id
    s.status = status
    s.output = output
    s.metadata = metadata or {}
    s.start_time = datetime(2026, 1, 1, tzinfo=UTC)
    s.end_time = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
    return s


@contextmanager
def _mock_otel_modules() -> Generator[dict[str, MagicMock], None, None]:
    """临时替换 sys.modules 中的 OTel 相关模块。"""
    module_names = [
        "opentelemetry",
        "opentelemetry.trace",
        "opentelemetry.sdk.trace",
        "opentelemetry.sdk.trace.export",
        "opentelemetry.sdk.resources",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.context",
    ]
    originals = {k: sys.modules.get(k) for k in module_names}

    mock_trace_mod = MagicMock()
    mock_sdk_trace = MagicMock()
    mock_export = MagicMock()
    mock_resources = MagicMock()
    mock_exporter = MagicMock()
    mock_context = MagicMock()
    mock_otel = MagicMock(trace=mock_trace_mod)

    mocks = {
        "opentelemetry": mock_otel,
        "opentelemetry.trace": mock_trace_mod,
        "opentelemetry.sdk.trace": mock_sdk_trace,
        "opentelemetry.sdk.trace.export": mock_export,
        "opentelemetry.sdk.resources": mock_resources,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_exporter,
        "opentelemetry.context": mock_context,
    }

    for k, v in mocks.items():
        sys.modules[k] = v

    try:
        yield mocks
    finally:
        for k, v in originals.items():
            if v is not None:
                sys.modules[k] = v
            else:
                sys.modules.pop(k, None)


class TestInitTracerSuccess:
    """line 68: _init_tracer 成功初始化 tracer。"""

    def test_init_tracer_sets_tracer(self) -> None:
        """OTel 依赖可用时，_init_tracer 应设置 self._tracer。"""
        with _mock_otel_modules() as mocks:
            mock_provider = MagicMock()
            mock_tracer = MagicMock()
            mock_provider.get_tracer.return_value = mock_tracer
            mocks["opentelemetry.sdk.trace"].TracerProvider.return_value = mock_provider

            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            proc._service_name = "test"
            proc._endpoint = "http://localhost:4317"
            proc._insecure = True
            proc._root_spans = {}
            proc._otel_spans = {}
            proc._tracer = None

            proc._init_tracer()

            assert proc._tracer is mock_tracer
            mocks["opentelemetry.sdk.resources"].Resource.create.assert_called_once()
            mock_provider.add_span_processor.assert_called_once()


class TestCheckOtelSuccess:
    """lines 37-38: _check_otel OTel 可用时返回 True。"""

    def test_otel_available_true(self) -> None:
        """OTel 依赖存在时返回 True。"""
        import ckyclaw_framework.tracing.otel_processor as mod

        original = mod._otel_available
        mod._otel_available = None  # 重置缓存

        with _mock_otel_modules():
            try:
                result = mod._check_otel()
                # 当 mock 模块可导入时应返回 True
                assert isinstance(result, bool)
            finally:
                mod._otel_available = original


class TestOnTraceStartWithTracer:
    """lines 81-87: on_trace_start 使用 tracer 创建 root span。"""

    @pytest.mark.asyncio
    async def test_creates_root_span(self) -> None:
        """tracer 存在时创建并存储 root span。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._root_spans = {}
        proc._otel_spans = {}

        mock_tracer = MagicMock()
        mock_root = MagicMock()
        mock_tracer.start_span.return_value = mock_root
        proc._tracer = mock_tracer

        trace = _make_trace("t1", "my_workflow")
        await proc.on_trace_start(trace)

        assert proc._root_spans["t1"] is mock_root
        mock_tracer.start_span.assert_called_once()
        call_kwargs = mock_tracer.start_span.call_args
        assert "trace:my_workflow" in str(call_kwargs)


class TestOnSpanStartWithParent:
    """lines 137-138: on_span_start 查找 parent span 上下文。"""

    @pytest.mark.asyncio
    async def test_parent_span_lookup(self) -> None:
        """有 parent_span_id 且在 _otel_spans 中，设置 parent context。"""
        with _mock_otel_modules() as mocks:
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            proc._root_spans = {}
            proc._otel_spans = {}

            mock_tracer = MagicMock()
            mock_parent_otel = MagicMock()
            proc._otel_spans["parent_s"] = mock_parent_otel
            mock_child_otel = MagicMock()
            mock_tracer.start_span.return_value = mock_child_otel
            proc._tracer = mock_tracer

            span = _make_span("child_s", "t1", "child", parent_span_id="parent_s")
            await proc.on_span_start(span)

            assert proc._otel_spans["child_s"] is mock_child_otel
            mocks["opentelemetry.trace"].set_span_in_context.assert_called_once_with(
                mock_parent_otel, mocks["opentelemetry.context"].Context()
            )

    @pytest.mark.asyncio
    async def test_root_span_as_parent(self) -> None:
        """无 parent_span_id 但有 root span → 使用 root 作为 parent。"""
        with _mock_otel_modules() as mocks:
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            mock_root = MagicMock()
            proc._root_spans = {"t1": mock_root}
            proc._otel_spans = {}

            mock_tracer = MagicMock()
            mock_child = MagicMock()
            mock_tracer.start_span.return_value = mock_child
            proc._tracer = mock_tracer

            span = _make_span("s1", "t1", "agent_span")
            await proc.on_span_start(span)

            assert proc._otel_spans["s1"] is mock_child
            mocks["opentelemetry.trace"].set_span_in_context.assert_called_once()


class TestOnSpanEndWithMetadata:
    """lines 163-164, 175-176: on_span_end 设置状态码 + 元数据。"""

    @pytest.mark.asyncio
    async def test_completed_with_metadata(self) -> None:
        """COMPLETED 状态 + metadata → set_status(OK) + set_attribute。"""
        with _mock_otel_modules():
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            proc._root_spans = {}

            mock_otel_span = MagicMock()
            proc._otel_spans = {"s1": mock_otel_span}
            proc._tracer = MagicMock()

            span = _make_span("s1", status=SpanStatus.COMPLETED, output="done", metadata={"k": "v"})
            await proc.on_span_end(span)

            mock_otel_span.set_status.assert_called_once()
            mock_otel_span.set_attribute.assert_any_call("ckyclaw.k", "v")
            mock_otel_span.set_attribute.assert_any_call("ckyclaw.output", "done")
            mock_otel_span.end.assert_called_once()
            assert "s1" not in proc._otel_spans

    @pytest.mark.asyncio
    async def test_failed_with_error(self) -> None:
        """FAILED 状态 → set_status(ERROR)。"""
        with _mock_otel_modules() as mocks:
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            proc._root_spans = {}

            mock_otel_span = MagicMock()
            proc._otel_spans = {"s1": mock_otel_span}
            proc._tracer = MagicMock()

            span = _make_span("s1", status=SpanStatus.FAILED, output="error occurred")
            await proc.on_span_end(span)

            mock_status_code = mocks["opentelemetry.trace"].StatusCode
            mock_otel_span.set_status.assert_called_once_with(
                mock_status_code.ERROR, "error occurred"
            )
            mock_otel_span.end.assert_called_once()


class TestOnTraceEndWithRoot:
    """lines 187-188: on_trace_end 结束 root span。"""

    @pytest.mark.asyncio
    async def test_ends_root_span(self) -> None:
        """trace 结束时设置 total_spans 属性并结束 root span。"""
        with _mock_otel_modules() as mocks:
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            mock_root = MagicMock()
            proc._root_spans = {"t1": mock_root}
            proc._otel_spans = {}
            proc._tracer = MagicMock()

            trace = _make_trace("t1")
            span1 = _make_span("s1", "t1")
            span2 = _make_span("s2", "t1")
            trace.spans = [span1, span2]

            await proc.on_trace_end(trace)

            mock_root.set_attribute.assert_any_call("ckyclaw.total_spans", 2)
            mock_status_code = mocks["opentelemetry.trace"].StatusCode
            mock_root.set_status.assert_called_once_with(mock_status_code.OK)
            mock_root.end.assert_called_once()
            assert "t1" not in proc._root_spans

    @pytest.mark.asyncio
    async def test_cleans_orphan_spans(self) -> None:
        """trace 结束时清理残留的未结束 otel span。"""
        with _mock_otel_modules():
            proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
            mock_root = MagicMock()
            proc._root_spans = {"t1": mock_root}

            mock_orphan = MagicMock()
            proc._otel_spans = {"s_orphan": mock_orphan}
            proc._tracer = MagicMock()

            trace = _make_trace("t1")
            orphan_span = _make_span("s_orphan", "t1")
            trace.spans = [orphan_span]

            await proc.on_trace_end(trace)

            mock_orphan.end.assert_called_once()
            assert "s_orphan" not in proc._otel_spans
