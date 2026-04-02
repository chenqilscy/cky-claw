"""PostgreSQL TraceProcessor — 将 Framework Trace/Span 持久化到数据库。"""

from __future__ import annotations

import logging
from typing import Any

from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span
from ckyclaw_framework.tracing.trace import Trace

logger = logging.getLogger(__name__)


class PostgresTraceProcessor(TraceProcessor):
    """收集 Trace/Span 数据，在 Trace 结束时批量写入。

    注意：此 Processor 不自行管理数据库会话。它只收集数据，
    调用方在 Trace 结束后通过 ``get_collected_data()`` 获取收集的数据，
    然后使用已有的 AsyncSession 写入数据库。
    """

    def __init__(self, *, session_id: str | None = None) -> None:
        self._session_id = session_id
        self._trace_data: dict[str, Any] | None = None
        self._span_data: list[dict[str, Any]] = []

    async def on_trace_start(self, trace: Trace) -> None:
        self._trace_data = {
            "id": trace.trace_id,
            "workflow_name": trace.workflow_name,
            "group_id": trace.group_id,
            "session_id": self._session_id,
            "start_time": trace.start_time,
        }

    async def on_span_start(self, span: Span) -> None:
        pass  # Span 数据在 on_span_end 中收集

    async def on_span_end(self, span: Span) -> None:
        input_data = _safe_serialize(span.input) if span.input is not None else None
        output_data = _safe_serialize(span.output) if span.output is not None else None

        self._span_data.append({
            "id": span.span_id,
            "trace_id": span.trace_id,
            "parent_span_id": span.parent_span_id,
            "type": span.type.value if hasattr(span.type, "value") else str(span.type),
            "name": span.name,
            "status": span.status.value if hasattr(span.status, "value") else str(span.status),
            "start_time": span.start_time,
            "end_time": span.end_time,
            "input_data": input_data,
            "output_data": output_data,
            "metadata_": span.metadata or {},
            "model": span.model,
            "token_usage": span.token_usage,
        })

    async def on_trace_end(self, trace: Trace) -> None:
        if self._trace_data is not None:
            self._trace_data["end_time"] = trace.end_time
            self._trace_data["span_count"] = len(trace.spans)
            # 从第一个 agent span 提取 agent_name
            for span in trace.spans:
                span_type = span.type.value if hasattr(span.type, "value") else str(span.type)
                if span_type == "agent" and span.parent_span_id is None:
                    self._trace_data["agent_name"] = span.name
                    break

    def get_collected_data(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """获取收集的 Trace/Span 数据。"""
        return self._trace_data, self._span_data


def _safe_serialize(value: Any) -> dict[str, Any] | None:
    """安全地将值转换为 JSON-compatible dict。"""
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, str):
        return {"text": value}
    if isinstance(value, list):
        return {"items": [str(item) for item in value]}
    try:
        return {"value": str(value)}
    except Exception:
        return None
