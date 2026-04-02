"""Trace 查询业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.trace import SpanRecord, TraceRecord


async def list_traces(
    db: AsyncSession,
    *,
    session_id: uuid.UUID | None = None,
    agent_name: str | None = None,
    workflow_name: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
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
    if start_time is not None:
        base = base.where(TraceRecord.start_time >= start_time)
    if end_time is not None:
        base = base.where(TraceRecord.start_time <= end_time)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(TraceRecord.start_time.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


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
