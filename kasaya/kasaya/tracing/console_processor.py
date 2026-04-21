"""ConsoleTraceProcessor — 将 Trace/Span 输出到控制台（调试用）。"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from kasaya.tracing.processor import TraceProcessor

if TYPE_CHECKING:
    from kasaya.tracing.span import Span
    from kasaya.tracing.trace import Trace

logger = logging.getLogger(__name__)


class ConsoleTraceProcessor(TraceProcessor):
    """将 Trace/Span 生命周期事件输出到日志。"""

    async def on_trace_start(self, trace: Trace) -> None:
        logger.info(
            "[Trace Start] trace_id=%s workflow=%s",
            trace.trace_id,
            trace.workflow_name,
        )

    async def on_span_start(self, span: Span) -> None:
        logger.info(
            "[Span Start] span_id=%s type=%s name=%s parent=%s",
            span.span_id,
            span.type.value,
            span.name,
            span.parent_span_id,
        )

    async def on_span_end(self, span: Span) -> None:
        duration = ""
        if span.end_time and span.start_time:
            ms = (span.end_time - span.start_time).total_seconds() * 1000
            duration = f" duration={ms:.1f}ms"
        token_info = ""
        if span.token_usage:
            token_info = f" tokens={json.dumps(span.token_usage)}"
        logger.info(
            "[Span End] span_id=%s type=%s name=%s status=%s%s%s",
            span.span_id,
            span.type.value,
            span.name,
            span.status.value,
            duration,
            token_info,
        )

    async def on_trace_end(self, trace: Trace) -> None:
        duration = ""
        if trace.end_time and trace.start_time:
            ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            duration = f" duration={ms:.1f}ms"
        logger.info(
            "[Trace End] trace_id=%s spans=%d%s",
            trace.trace_id,
            len(trace.spans),
            duration,
        )
