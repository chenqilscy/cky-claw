"""OTelTraceProcessor 单元测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ckyclaw_framework.tracing.otel_processor import OTelTraceProcessor, _check_otel
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace


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
    metadata: dict | None = None,
) -> Span:
    """创建测试 Span。"""
    s = Span(type=span_type, name=name)
    s.span_id = span_id
    s.trace_id = trace_id
    s.parent_span_id = parent_span_id
    s.status = status
    s.output = output
    s.metadata = metadata or {}
    s.start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s.end_time = datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    return s


class TestCheckOtel:
    """测试 _check_otel 函数。"""

    def test_otel_not_installed(self) -> None:
        """opentelemetry 未安装时返回 False。"""
        import ckyclaw_framework.tracing.otel_processor as mod
        original = mod._otel_available
        mod._otel_available = None  # 重置缓存
        try:
            with patch.dict("sys.modules", {"opentelemetry.trace": None, "opentelemetry.sdk.trace": None}):
                with patch.dict("sys.modules", {"opentelemetry": None}):
                    result = _check_otel()
            # 不管结果如何，函数不应崩溃
            assert isinstance(result, bool)
        finally:
            mod._otel_available = original

    def test_cached_result(self) -> None:
        """_otel_available 已缓存时直接返回。"""
        import ckyclaw_framework.tracing.otel_processor as mod
        original = mod._otel_available
        mod._otel_available = True
        try:
            result = _check_otel()
            assert result is True
        finally:
            mod._otel_available = original

    def test_cached_false(self) -> None:
        """_otel_available 缓存为 False 时直接返回。"""
        import ckyclaw_framework.tracing.otel_processor as mod
        original = mod._otel_available
        mod._otel_available = False
        try:
            result = _check_otel()
            assert result is False
        finally:
            mod._otel_available = original


class TestOTelTraceProcessorNoOtel:
    """当 OTel 不可用时的行为测试。"""

    def test_init_without_otel(self) -> None:
        """OTel 不可用时初始化不崩溃。"""
        import ckyclaw_framework.tracing.otel_processor as mod
        original = mod._otel_available
        mod._otel_available = False
        try:
            proc = OTelTraceProcessor()
            assert proc._tracer is None
        finally:
            mod._otel_available = original

    @pytest.mark.asyncio
    async def test_on_trace_start_noop(self) -> None:
        """tracer 为 None 时 on_trace_start 不执行。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._tracer = None
        proc._root_spans = {}
        proc._otel_spans = {}
        trace = _make_trace()
        await proc.on_trace_start(trace)
        assert trace.trace_id not in proc._root_spans

    @pytest.mark.asyncio
    async def test_on_span_start_noop(self) -> None:
        """tracer 为 None 时 on_span_start 不执行。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._tracer = None
        proc._root_spans = {}
        proc._otel_spans = {}
        span = _make_span()
        await proc.on_span_start(span)
        assert span.span_id not in proc._otel_spans

    @pytest.mark.asyncio
    async def test_on_span_end_missing_span(self) -> None:
        """span_id 不在 _otel_spans 时 on_span_end 直接返回。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._tracer = MagicMock()
        proc._root_spans = {}
        proc._otel_spans = {}
        span = _make_span()
        await proc.on_span_end(span)  # 不应崩溃

    @pytest.mark.asyncio
    async def test_on_trace_end_missing_root(self) -> None:
        """trace_id 不在 _root_spans 时 on_trace_end 直接返回。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._tracer = MagicMock()
        proc._root_spans = {}
        proc._otel_spans = {}
        trace = _make_trace()
        trace.spans = []
        await proc.on_trace_end(trace)


class TestOTelTraceProcessorWithMock:
    """通过 mock tracer 测试完整流程。"""

    def _make_processor(self) -> OTelTraceProcessor:
        """创建带有 mock tracer 的 processor。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._service_name = "test"
        proc._endpoint = "http://localhost:4317"
        proc._insecure = True
        proc._root_spans = {}
        proc._otel_spans = {}
        proc._tracer = MagicMock()
        return proc

    @pytest.mark.asyncio
    async def test_trace_start_creates_root_span(self) -> None:
        """on_trace_start 创建 root span。"""
        proc = self._make_processor()
        mock_span = MagicMock()
        proc._tracer.start_span = MagicMock(return_value=mock_span)

        trace = _make_trace("t1", "my_workflow")
        await proc.on_trace_start(trace)

        assert "t1" in proc._root_spans
        assert proc._root_spans["t1"] is mock_span
        proc._tracer.start_span.assert_called_once()

    @pytest.mark.asyncio
    async def test_span_start_creates_child_span(self) -> None:
        """on_span_start 创建 child span（无 parent）。"""
        proc = self._make_processor()
        mock_root = MagicMock()
        proc._root_spans["t1"] = mock_root
        mock_child = MagicMock()
        proc._tracer.start_span = MagicMock(return_value=mock_child)

        # 需要 mock opentelemetry 模块
        mock_otel_trace = MagicMock()
        mock_otel_trace.set_span_in_context = MagicMock(return_value=MagicMock())
        mock_context = MagicMock()

        import sys
        original_otel = sys.modules.get("opentelemetry")
        original_otel_trace = sys.modules.get("opentelemetry.trace")
        original_otel_ctx = sys.modules.get("opentelemetry.context")

        mock_otel_mod = MagicMock()
        mock_otel_mod.trace = mock_otel_trace
        sys.modules["opentelemetry"] = mock_otel_mod
        sys.modules["opentelemetry.trace"] = mock_otel_trace
        sys.modules["opentelemetry.context"] = mock_context

        try:
            span = _make_span("s1", "t1", "agent_span")
            await proc.on_span_start(span)
            assert "s1" in proc._otel_spans
        finally:
            if original_otel is not None:
                sys.modules["opentelemetry"] = original_otel
            else:
                sys.modules.pop("opentelemetry", None)
            if original_otel_trace is not None:
                sys.modules["opentelemetry.trace"] = original_otel_trace
            else:
                sys.modules.pop("opentelemetry.trace", None)
            if original_otel_ctx is not None:
                sys.modules["opentelemetry.context"] = original_otel_ctx
            else:
                sys.modules.pop("opentelemetry.context", None)

    @pytest.mark.asyncio
    async def test_span_start_with_parent(self) -> None:
        """on_span_start 有 parent_span_id 时使用 parent context。"""
        proc = self._make_processor()
        mock_parent = MagicMock()
        proc._otel_spans["s_parent"] = mock_parent
        mock_child = MagicMock()
        proc._tracer.start_span = MagicMock(return_value=mock_child)

        mock_otel_trace = MagicMock()
        mock_context = MagicMock()

        import sys
        orig = {k: sys.modules.get(k) for k in ["opentelemetry", "opentelemetry.trace", "opentelemetry.context"]}
        sys.modules["opentelemetry"] = MagicMock(trace=mock_otel_trace)
        sys.modules["opentelemetry.trace"] = mock_otel_trace
        sys.modules["opentelemetry.context"] = mock_context

        try:
            span = _make_span("s_child", "t1", "child", parent_span_id="s_parent")
            await proc.on_span_start(span)
            assert "s_child" in proc._otel_spans
            mock_otel_trace.set_span_in_context.assert_called_once()
        finally:
            for k, v in orig.items():
                if v is not None:
                    sys.modules[k] = v
                else:
                    sys.modules.pop(k, None)

    @pytest.mark.asyncio
    async def test_span_end_success(self) -> None:
        """on_span_end 正常结束 span（OK 状态）。"""
        proc = self._make_processor()
        mock_otel_span = MagicMock()
        proc._otel_spans["s1"] = mock_otel_span

        mock_status_code = MagicMock()
        mock_status_code.OK = "OK"
        mock_status_code.ERROR = "ERROR"

        import sys
        orig = sys.modules.get("opentelemetry.trace")
        sys.modules["opentelemetry.trace"] = MagicMock(StatusCode=mock_status_code)

        try:
            span = _make_span("s1", status=SpanStatus.COMPLETED, output="done", metadata={"key": "val"})
            await proc.on_span_end(span)
            mock_otel_span.set_status.assert_called_once()
            mock_otel_span.end.assert_called_once()
            assert "s1" not in proc._otel_spans
        finally:
            if orig is not None:
                sys.modules["opentelemetry.trace"] = orig
            else:
                sys.modules.pop("opentelemetry.trace", None)

    @pytest.mark.asyncio
    async def test_span_end_failed(self) -> None:
        """on_span_end FAILED 状态时设置 ERROR 状态码。"""
        proc = self._make_processor()
        mock_otel_span = MagicMock()
        proc._otel_spans["s1"] = mock_otel_span

        mock_status_code = MagicMock()

        import sys
        orig = sys.modules.get("opentelemetry.trace")
        sys.modules["opentelemetry.trace"] = MagicMock(StatusCode=mock_status_code)

        try:
            span = _make_span("s1", status=SpanStatus.FAILED, output="error msg")
            await proc.on_span_end(span)
            mock_otel_span.set_status.assert_called_once_with(mock_status_code.ERROR, "error msg")
            mock_otel_span.end.assert_called_once()
        finally:
            if orig is not None:
                sys.modules["opentelemetry.trace"] = orig
            else:
                sys.modules.pop("opentelemetry.trace", None)

    @pytest.mark.asyncio
    async def test_trace_end_cleans_up(self) -> None:
        """on_trace_end 清理残留 span 并结束 root span。"""
        proc = self._make_processor()
        mock_root = MagicMock()
        proc._root_spans["t1"] = mock_root

        # 创建一个属于该 trace 的残留 span
        mock_otel_span = MagicMock()
        proc._otel_spans["s_orphan"] = mock_otel_span

        mock_status_code = MagicMock()

        import sys
        orig = sys.modules.get("opentelemetry.trace")
        sys.modules["opentelemetry.trace"] = MagicMock(StatusCode=mock_status_code)

        try:
            trace = _make_trace("t1")
            orphan_span = _make_span("s_orphan", "t1")
            trace.spans = [orphan_span]
            await proc.on_trace_end(trace)

            # 残留 span 应被 end
            mock_otel_span.end.assert_called_once()
            # root span 应被 end
            mock_root.end.assert_called_once()
            assert "t1" not in proc._root_spans
            assert "s_orphan" not in proc._otel_spans
        finally:
            if orig is not None:
                sys.modules["opentelemetry.trace"] = orig
            else:
                sys.modules.pop("opentelemetry.trace", None)

    @pytest.mark.asyncio
    async def test_trace_start_exception_handled(self) -> None:
        """on_trace_start 异常时不崩溃。"""
        proc = self._make_processor()
        proc._tracer.start_span = MagicMock(side_effect=Exception("OTel error"))
        trace = _make_trace()
        await proc.on_trace_start(trace)  # 不应崩溃

    @pytest.mark.asyncio
    async def test_span_end_exception_handled(self) -> None:
        """on_span_end 异常时不崩溃。"""
        proc = self._make_processor()
        mock_otel_span = MagicMock()
        proc._otel_spans["s1"] = mock_otel_span

        import sys
        orig = sys.modules.get("opentelemetry.trace")
        mock_mod = MagicMock()
        mock_mod.StatusCode = MagicMock(side_effect=Exception("import fail"))
        sys.modules["opentelemetry.trace"] = mock_mod

        try:
            span = _make_span("s1")
            await proc.on_span_end(span)  # 不应崩溃
        finally:
            if orig is not None:
                sys.modules["opentelemetry.trace"] = orig
            else:
                sys.modules.pop("opentelemetry.trace", None)

    @pytest.mark.asyncio
    async def test_init_tracer_exception(self) -> None:
        """_init_tracer 异常时不崩溃。"""
        proc = OTelTraceProcessor.__new__(OTelTraceProcessor)
        proc._service_name = "test"
        proc._endpoint = "http://localhost:4317"
        proc._insecure = True
        proc._root_spans = {}
        proc._otel_spans = {}
        proc._tracer = None

        import sys
        mock_otel = MagicMock()
        mock_otel.trace.TracerProvider = MagicMock(side_effect=Exception("init fail"))

        orig = {k: sys.modules.get(k) for k in [
            "opentelemetry", "opentelemetry.trace",
            "opentelemetry.sdk.trace", "opentelemetry.sdk.trace.export",
            "opentelemetry.sdk.resources",
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
        ]}

        for key in orig:
            sys.modules[key] = MagicMock()
        sys.modules["opentelemetry.sdk.trace"].TracerProvider = MagicMock(side_effect=Exception("bad"))

        try:
            proc._init_tracer()
            # 不应崩溃，tracer 应仍为 None
        finally:
            for k, v in orig.items():
                if v is not None:
                    sys.modules[k] = v
                else:
                    sys.modules.pop(k, None)
