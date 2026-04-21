"""EventJournalProcessor — 将 Trace/Span 事件转换为 EventEntry 写入 EventJournal。

实现 TraceProcessor 接口，作为 trace_processors 列表的一员，
在 Runner 运行过程中自动将 Span 生命周期事件转化为细粒度 EventEntry。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from kasaya.events.journal import EventEntry, EventJournal
from kasaya.events.types import EventType
from kasaya.tracing.processor import TraceProcessor
from kasaya.tracing.span import Span, SpanStatus, SpanType

if TYPE_CHECKING:
    from kasaya.events.projector import Projector
    from kasaya.tracing.trace import Trace

logger = logging.getLogger(__name__)

# ── SpanType → EventType 映射 ──
_SPAN_START_MAP: dict[SpanType, EventType] = {
    SpanType.AGENT: EventType.AGENT_START,
    SpanType.LLM: EventType.LLM_CALL_START,
    SpanType.TOOL: EventType.TOOL_CALL_START,
    SpanType.HANDOFF: EventType.HANDOFF,
    SpanType.GUARDRAIL: EventType.GUARDRAIL_CHECK_START,
}

_SPAN_END_MAP: dict[SpanType, EventType] = {
    SpanType.AGENT: EventType.AGENT_END,
    SpanType.LLM: EventType.LLM_CALL_END,
    SpanType.TOOL: EventType.TOOL_CALL_END,
    SpanType.GUARDRAIL: EventType.GUARDRAIL_CHECK_END,
}


class EventJournalProcessor(TraceProcessor):
    """将 Trace/Span 生命周期事件写入 EventJournal。

    用法::

        journal = InMemoryEventJournal()
        processor = EventJournalProcessor(
            journal=journal,
            run_id="run-123",
            session_id="sess-456",
        )
        config = RunConfig(trace_processors=[processor])
    """

    def __init__(
        self,
        journal: EventJournal,
        *,
        run_id: str = "",
        session_id: str | None = None,
        projectors: list[Projector] | None = None,
    ) -> None:
        self._journal = journal
        self._run_id = run_id
        self._session_id = session_id
        self._projectors = list(projectors or [])

    @property
    def journal(self) -> EventJournal:
        """关联的 EventJournal。"""
        return self._journal

    async def on_trace_start(self, trace: Trace) -> None:
        """Trace 开始 → RUN_START 事件。"""
        entry = EventEntry(
            event_type=EventType.RUN_START,
            run_id=self._run_id,
            session_id=self._session_id,
            payload={
                "trace_id": trace.trace_id,
                "workflow_name": trace.workflow_name,
                "group_id": trace.group_id,
            },
        )
        await self._emit(entry)

    async def on_span_start(self, span: Span) -> None:
        """Span 开始 → 对应类型的 START 事件。"""
        event_type = _SPAN_START_MAP.get(span.type)
        if event_type is None:
            return

        payload = self._build_span_payload(span)
        entry = EventEntry(
            event_type=event_type,
            run_id=self._run_id,
            session_id=self._session_id,
            agent_name=span.name if span.type == SpanType.AGENT else None,
            span_id=span.span_id,
            payload=payload,
        )
        await self._emit(entry)

    async def on_span_end(self, span: Span) -> None:
        """Span 结束 → 对应类型的 END 事件（含额外检测）。"""
        event_type = _SPAN_END_MAP.get(span.type)

        # Guardrail tripwire 检测
        if span.type == SpanType.GUARDRAIL and span.status == SpanStatus.FAILED:
            tripwire_entry = EventEntry(
                event_type=EventType.GUARDRAIL_TRIPWIRE,
                run_id=self._run_id,
                session_id=self._session_id,
                span_id=span.span_id,
                payload={
                    "guardrail_name": span.name,
                    "message": span.output if isinstance(span.output, str) else str(span.output or ""),
                    **self._build_span_payload(span),
                },
            )
            await self._emit(tripwire_entry)

        # Error 事件检测
        if span.status == SpanStatus.FAILED and span.type != SpanType.GUARDRAIL:
            error_entry = EventEntry(
                event_type=EventType.ERROR,
                run_id=self._run_id,
                session_id=self._session_id,
                span_id=span.span_id,
                agent_name=span.name if span.type == SpanType.AGENT else None,
                payload={
                    "span_type": span.type.value,
                    "span_name": span.name,
                    "error": span.output if isinstance(span.output, str) else str(span.output or ""),
                    "duration_ms": span.duration_ms,
                },
            )
            await self._emit(error_entry)

        if event_type is None:
            return

        payload = self._build_span_payload(span)
        payload["status"] = span.status.value
        payload["duration_ms"] = span.duration_ms

        # LLM 特有字段
        if span.type == SpanType.LLM:
            if span.token_usage:
                payload["token_usage"] = span.token_usage
            if span.model:
                payload["model"] = span.model

        # Tool 特有字段
        if span.type == SpanType.TOOL:
            payload["output"] = span.output if isinstance(span.output, str) else str(span.output or "")

        entry = EventEntry(
            event_type=event_type,
            run_id=self._run_id,
            session_id=self._session_id,
            agent_name=span.name if span.type == SpanType.AGENT else None,
            span_id=span.span_id,
            payload=payload,
        )
        await self._emit(entry)

    async def on_trace_end(self, trace: Trace) -> None:
        """Trace 结束 → RUN_END 事件。"""
        entry = EventEntry(
            event_type=EventType.RUN_END,
            run_id=self._run_id,
            session_id=self._session_id,
            payload={
                "trace_id": trace.trace_id,
                "span_count": len(trace.spans),
                "duration_ms": (
                    int((trace.end_time - trace.start_time).total_seconds() * 1000)
                    if trace.end_time
                    else None
                ),
            },
        )
        await self._emit(entry)

    async def _emit(self, entry: EventEntry) -> None:
        """写入 Journal 并通知 Projector。"""
        try:
            await self._journal.append(entry)
        except Exception:
            logger.exception("EventJournal append failed for event %s", entry.event_type.value)
            return

        # 通知所有 Projector
        for projector in self._projectors:
            try:
                await projector.on_event(entry)
            except Exception:
                logger.exception(
                    "Projector '%s' failed for event %s",
                    type(projector).__name__,
                    entry.event_type.value,
                )

    @staticmethod
    def _build_span_payload(span: Span) -> dict[str, Any]:
        """构建 Span 通用 payload。"""
        payload: dict[str, Any] = {
            "span_id": span.span_id,
            "span_name": span.name,
            "span_type": span.type.value,
        }
        if span.parent_span_id:
            payload["parent_span_id"] = span.parent_span_id
        if span.metadata:
            payload["metadata"] = span.metadata
        return payload
