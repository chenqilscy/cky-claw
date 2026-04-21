"""Events Replay API — 事件日志查询与回放。"""

from __future__ import annotations
import uuid

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.deps import get_db, require_permission
from app.models.event import EventRecord

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/events", tags=["events"])


# ── Schemas ──


class EventResponse(BaseModel):
    """单条事件响应。"""

    event_id: str
    sequence: int
    event_type: str
    run_id: str
    session_id: str | None = None
    agent_name: str | None = None
    span_id: str | None = None
    timestamp: datetime
    payload: dict | None = None

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    """事件列表响应。"""

    items: list[EventResponse]
    total: int = 0


class EventStatsResponse(BaseModel):
    """事件统计响应。"""

    total_events: int = 0
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    run_count: int = 0


# ── 路由 ──


@router.get(
    "/replay/{run_id}",
    response_model=EventListResponse,
    dependencies=[Depends(require_permission("traces", "read"))],
)
async def replay_run_events(
    run_id: str,
    event_type: str | None = Query(None, description="按事件类型筛选"),
    after_sequence: int | None = Query(None, description="大于此序列号的事件"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回条数"),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    """按时间序返回指定 Run 的事件流（用于回放）。"""
    stmt = (
        select(EventRecord)
        .where(EventRecord.run_id == run_id)
        .order_by(EventRecord.sequence.asc())
    )

    if event_type:
        stmt = stmt.where(EventRecord.event_type == event_type)
    if after_sequence is not None:
        stmt = stmt.where(EventRecord.sequence > after_sequence)

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    records = result.scalars().all()

    # 总数查询
    count_stmt = select(func.count()).select_from(EventRecord).where(EventRecord.run_id == run_id)
    if event_type:
        count_stmt = count_stmt.where(EventRecord.event_type == event_type)
    total = (await db.execute(count_stmt)).scalar() or 0

    return EventListResponse(
        items=[
            EventResponse(
                event_id=str(r.id),
                sequence=r.sequence,
                event_type=r.event_type,
                run_id=r.run_id,
                session_id=str(r.session_id) if r.session_id else None,
                agent_name=r.agent_name,
                span_id=r.span_id,
                timestamp=r.timestamp,
                payload=r.payload,
            )
            for r in records
        ],
        total=total,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=EventListResponse,
    dependencies=[Depends(require_permission("traces", "read"))],
)
async def get_session_events(
    session_id: uuid.UUID,
    event_type: str | None = Query(None, description="按事件类型筛选"),
    limit: int = Query(200, ge=1, le=1000, description="最大返回条数"),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    """获取指定 Session 的所有事件。"""
    stmt = (
        select(EventRecord)
        .where(EventRecord.session_id == session_id)
        .order_by(EventRecord.sequence.asc())
    )

    if event_type:
        stmt = stmt.where(EventRecord.event_type == event_type)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    records = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(EventRecord)
        .where(EventRecord.session_id == session_id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    return EventListResponse(
        items=[
            EventResponse(
                event_id=str(r.id),
                sequence=r.sequence,
                event_type=r.event_type,
                run_id=r.run_id,
                session_id=str(r.session_id) if r.session_id else None,
                agent_name=r.agent_name,
                span_id=r.span_id,
                timestamp=r.timestamp,
                payload=r.payload,
            )
            for r in records
        ],
        total=total,
    )


@router.get(
    "/stats",
    response_model=EventStatsResponse,
    dependencies=[Depends(require_permission("traces", "read"))],
)
async def get_event_stats(
    run_id: str | None = Query(None, description="按 Run ID 筛选"),
    session_id: uuid.UUID | None = Query(None, description="按 Session 筛选"),
    db: AsyncSession = Depends(get_db),
) -> EventStatsResponse:
    """获取事件统计。"""
    base_where = []
    if run_id:
        base_where.append(EventRecord.run_id == run_id)
    if session_id:
        base_where.append(EventRecord.session_id == session_id)

    # 总事件数
    total_stmt = select(func.count()).select_from(EventRecord)
    for w in base_where:
        total_stmt = total_stmt.where(w)
    total = (await db.execute(total_stmt)).scalar() or 0

    # 按类型分组计数
    type_stmt = (
        select(EventRecord.event_type, func.count())
        .group_by(EventRecord.event_type)
    )
    for w in base_where:
        type_stmt = type_stmt.where(w)
    type_results = (await db.execute(type_stmt)).all()
    type_counts = {row[0]: row[1] for row in type_results}

    # Run 数量
    run_stmt = (
        select(func.count(func.distinct(EventRecord.run_id)))
        .select_from(EventRecord)
    )
    for w in base_where:
        run_stmt = run_stmt.where(w)
    run_count = (await db.execute(run_stmt)).scalar() or 0

    return EventStatsResponse(
        total_events=total,
        event_type_counts=type_counts,
        run_count=run_count,
    )
