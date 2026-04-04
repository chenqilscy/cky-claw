"""Trace 查询业务逻辑层。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.trace import SpanRecord, TraceRecord


async def list_traces(
    db: AsyncSession,
    *,
    session_id: uuid.UUID | None = None,
    agent_name: str | None = None,
    workflow_name: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    has_guardrail_triggered: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TraceRecord], int]:
    """获取 Trace 列表（分页 + 多维筛选）。"""
    base = select(TraceRecord)

    if session_id is not None:
        base = base.where(TraceRecord.session_id == session_id)
    if agent_name is not None:
        base = base.where(TraceRecord.agent_name == agent_name)
    if workflow_name is not None:
        base = base.where(TraceRecord.workflow_name == workflow_name)
    if status is not None:
        base = base.where(TraceRecord.status == status)
    if start_time is not None:
        base = base.where(TraceRecord.start_time >= start_time)
    if end_time is not None:
        base = base.where(TraceRecord.start_time <= end_time)
    if min_duration_ms is not None:
        base = base.where(TraceRecord.duration_ms >= min_duration_ms)
    if max_duration_ms is not None:
        base = base.where(TraceRecord.duration_ms <= max_duration_ms)
    if has_guardrail_triggered is True:
        # 关联 spans 表查找有 guardrail 触发（status=failed）的 trace
        sub = (
            select(SpanRecord.trace_id)
            .where(SpanRecord.type == "guardrail", SpanRecord.status == "failed")
            .distinct()
        ).subquery()
        base = base.where(TraceRecord.id.in_(select(sub.c.trace_id)))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(TraceRecord.start_time.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def list_spans(
    db: AsyncSession,
    *,
    trace_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    name: str | None = None,
    min_duration_ms: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[SpanRecord], int]:
    """搜索 Span（分页 + 多维筛选）。"""
    base = select(SpanRecord)

    if trace_id is not None:
        base = base.where(SpanRecord.trace_id == trace_id)
    if type is not None:
        base = base.where(SpanRecord.type == type)
    if status is not None:
        base = base.where(SpanRecord.status == status)
    if name is not None:
        base = base.where(SpanRecord.name.ilike(f"%{name}%"))
    if min_duration_ms is not None:
        base = base.where(SpanRecord.duration_ms >= min_duration_ms)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(SpanRecord.start_time.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_trace_stats(
    db: AsyncSession,
    *,
    session_id: uuid.UUID | None = None,
    agent_name: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    """获取 Trace 统计数据。默认最近 7 天。"""
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(days=7)

    # ── Trace 级统计 ──
    trace_base = select(TraceRecord).where(TraceRecord.start_time >= start_time)
    if end_time is not None:
        trace_base = trace_base.where(TraceRecord.start_time <= end_time)
    if session_id is not None:
        trace_base = trace_base.where(TraceRecord.session_id == session_id)
    if agent_name is not None:
        trace_base = trace_base.where(TraceRecord.agent_name == agent_name)

    trace_sub = trace_base.subquery()
    trace_stats_stmt = select(
        func.count().label("total_traces"),
        func.avg(trace_sub.c.duration_ms).label("avg_duration_ms"),
        func.count(case((trace_sub.c.status == "failed", 1))).label("error_count"),
    ).select_from(trace_sub)
    trace_row = (await db.execute(trace_stats_stmt)).one()

    total_traces = trace_row.total_traces or 0
    avg_duration_ms = float(trace_row.avg_duration_ms) if trace_row.avg_duration_ms else None
    error_count = trace_row.error_count or 0
    error_rate = error_count / total_traces if total_traces > 0 else 0.0

    # ── Span 级统计 ──
    span_base = select(SpanRecord).where(SpanRecord.start_time >= start_time)
    if end_time is not None:
        span_base = span_base.where(SpanRecord.start_time <= end_time)

    span_sub = span_base.subquery()

    # 总 span 数
    total_spans_stmt = select(func.count()).select_from(span_sub)
    total_spans = (await db.execute(total_spans_stmt)).scalar_one() or 0

    # 按类型计数
    type_counts_stmt = (
        select(span_sub.c.type, func.count().label("cnt"))
        .select_from(span_sub)
        .group_by(span_sub.c.type)
    )
    type_rows = (await db.execute(type_counts_stmt)).all()
    span_type_counts = {row.type: row.cnt for row in type_rows}

    # Token 用量统计（从 LLM span 的 token_usage JSONB 聚合）
    llm_span_stmt = (
        select(span_sub.c.token_usage)
        .select_from(span_sub)
        .where(span_sub.c.type == "llm", span_sub.c.token_usage.isnot(None))
    )
    llm_rows = (await db.execute(llm_span_stmt)).all()
    prompt_tokens = 0
    completion_tokens = 0
    for row in llm_rows:
        tu = row.token_usage
        if isinstance(tu, dict):
            prompt_tokens += tu.get("prompt_tokens", 0)
            completion_tokens += tu.get("completion_tokens", 0)

    # Guardrail 统计
    guardrail_total = span_type_counts.get("guardrail", 0)
    guardrail_triggered_stmt = (
        select(func.count())
        .select_from(span_sub)
        .where(span_sub.c.type == "guardrail", span_sub.c.status == "failed")
    )
    guardrail_triggered = (await db.execute(guardrail_triggered_stmt)).scalar_one() or 0
    guardrail_trigger_rate = guardrail_triggered / guardrail_total if guardrail_total > 0 else 0.0

    return {
        "total_traces": total_traces,
        "total_spans": total_spans,
        "avg_duration_ms": avg_duration_ms,
        "total_tokens": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "span_type_counts": {
            "agent": span_type_counts.get("agent", 0),
            "llm": span_type_counts.get("llm", 0),
            "tool": span_type_counts.get("tool", 0),
            "handoff": span_type_counts.get("handoff", 0),
            "guardrail": span_type_counts.get("guardrail", 0),
        },
        "guardrail_stats": {
            "total": guardrail_total,
            "triggered": guardrail_triggered,
            "trigger_rate": round(guardrail_trigger_rate, 4),
        },
        "error_rate": round(error_rate, 4),
    }


async def get_trace_detail(
    db: AsyncSession,
    trace_id: str,
) -> tuple[TraceRecord, list[SpanRecord]]:
    """获取 Trace 详情（含所有 Span）。"""
    trace_stmt = select(TraceRecord).where(TraceRecord.id == trace_id)
    trace = (await db.execute(trace_stmt)).scalar_one_or_none()
    if trace is None:
        raise NotFoundError(f"Trace '{trace_id}' 不存在")

    spans_stmt = (
        select(SpanRecord)
        .where(SpanRecord.trace_id == trace_id)
        .order_by(SpanRecord.start_time.asc())
    )
    spans = list((await db.execute(spans_stmt)).scalars().all())

    return trace, spans


async def save_trace(
    db: AsyncSession,
    trace: TraceRecord,
    spans: list[SpanRecord],
) -> None:
    """保存 Trace 及其所有 Span。"""
    db.add(trace)
    if spans:
        db.add_all(spans)
    await db.flush()
