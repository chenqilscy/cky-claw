"""OpenTelemetry TraceProcessor — 将 Kasaya Tracing 数据导出到 OTel Collector。

使用方式：
    from kasaya.tracing.otel_processor import OTelTraceProcessor

    processor = OTelTraceProcessor(
        service_name="kasaya-agent",
        endpoint="http://localhost:4317",  # OTel Collector gRPC
    )

需要安装 opentelemetry 依赖：
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from kasaya.tracing.processor import TraceProcessor
from kasaya.tracing.span import Span, SpanStatus

if TYPE_CHECKING:
    from kasaya.tracing.trace import Trace

logger = logging.getLogger(__name__)

# 延迟导入 OTel SDK — 仅在实际使用时检查依赖
_otel_available: bool | None = None


def _check_otel() -> bool:
    """检查 opentelemetry 依赖是否可用。"""
    global _otel_available
    if _otel_available is not None:
        return _otel_available
    try:
        import opentelemetry.sdk.trace  # noqa: F401
        import opentelemetry.trace  # noqa: F401
        _otel_available = True
    except ImportError:
        _otel_available = False
        logger.warning(
            "opentelemetry packages not installed. "
            "Install: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc"
        )
    return _otel_available


class OTelTraceProcessor(TraceProcessor):
    """将 Kasaya 内部 Trace/Span 映射到 OpenTelemetry Span 并导出。

    每个 Kasaya Trace 创建一个 OTel root span，每个 Kasaya Span 映射为 OTel child span。
    """

    def __init__(
        self,
        service_name: str = "kasaya",
        endpoint: str = "http://localhost:4317",
        insecure: bool = True,
    ) -> None:
        self._service_name = service_name
        self._endpoint = endpoint
        self._insecure = insecure
        self._tracer: Any = None
        self._otel_spans: dict[str, Any] = {}  # span_id -> OTel Span
        self._root_spans: dict[str, Any] = {}  # trace_id -> OTel root Span

        if _check_otel():
            self._init_tracer()

    def _init_tracer(self) -> None:
        """初始化 OTel tracer + OTLP exporter。"""
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": self._service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(
                endpoint=self._endpoint,
                insecure=self._insecure,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
            self._tracer = provider.get_tracer("kasaya")
            logger.info("OTel TraceProcessor initialized: endpoint=%s", self._endpoint)
        except Exception as e:
            logger.error("Failed to initialize OTel tracer: %s", e)

    async def on_trace_start(self, trace: Trace) -> None:
        """Kasaya Trace 开始 → 创建 OTel root span。"""
        if self._tracer is None:
            return
        try:
            root_span = self._tracer.start_span(
                name=f"trace:{trace.workflow_name}",
                attributes={
                    "kasaya.trace_id": trace.trace_id,
                    "kasaya.workflow_name": trace.workflow_name,
                    "kasaya.group_id": trace.group_id or "",
                },
            )
            self._root_spans[trace.trace_id] = root_span
        except Exception as e:
            logger.debug("OTel on_trace_start error: %s", e)

    async def on_span_start(self, span: Span) -> None:
        """Kasaya Span 开始 → 创建 OTel child span。"""
        if self._tracer is None:
            return
        try:
            # 查找 parent context
            parent_span = None
            if span.parent_span_id and span.parent_span_id in self._otel_spans:
                parent_span = self._otel_spans[span.parent_span_id]
            elif span.trace_id in self._root_spans:
                parent_span = self._root_spans[span.trace_id]

            from opentelemetry import trace as otel_trace
            from opentelemetry.context import Context

            ctx = Context()
            if parent_span:
                ctx = otel_trace.set_span_in_context(parent_span, ctx)

            otel_span = self._tracer.start_span(
                name=f"{span.type.value}:{span.name}",
                context=ctx,
                attributes={
                    "kasaya.span_id": span.span_id,
                    "kasaya.type": span.type.value,
                    "kasaya.name": span.name,
                },
            )
            self._otel_spans[span.span_id] = otel_span
        except Exception as e:
            logger.debug("OTel on_span_start error: %s", e)

    async def on_span_end(self, span: Span) -> None:
        """Kasaya Span 结束 → 结束 OTel span。"""
        otel_span = self._otel_spans.pop(span.span_id, None)
        if otel_span is None:
            return
        try:
            from opentelemetry.trace import StatusCode

            # 设置状态
            if span.status == SpanStatus.FAILED:
                otel_span.set_status(StatusCode.ERROR, span.output or "")
            else:
                otel_span.set_status(StatusCode.OK)

            # 添加元数据
            if span.metadata:
                for k, v in span.metadata.items():
                    otel_span.set_attribute(f"kasaya.{k}", str(v))

            if span.output:
                otel_span.set_attribute("kasaya.output", str(span.output)[:1024])

            otel_span.end()
        except Exception as e:
            logger.debug("OTel on_span_end error: %s", e)

    async def on_trace_end(self, trace: Trace) -> None:
        """Kasaya Trace 结束 → 结束 root span。"""
        # 清理该 trace 下残留的未结束 span（仅清理属于此 trace 的 span）
        trace_span_ids = {s.span_id for s in trace.spans}
        for sid in trace_span_ids:
            otel_span = self._otel_spans.pop(sid, None)
            if otel_span:
                with contextlib.suppress(Exception):
                    otel_span.end()

        root_span = self._root_spans.pop(trace.trace_id, None)
        if root_span is None:
            return
        try:
            from opentelemetry.trace import StatusCode

            root_span.set_attribute("kasaya.total_spans", len(trace.spans))
            root_span.set_status(StatusCode.OK)
            root_span.end()
        except Exception as e:
            logger.debug("OTel on_trace_end error: %s", e)
