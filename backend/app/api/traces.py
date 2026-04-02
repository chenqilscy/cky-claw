"""Trace 查询 API。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.trace import TraceDetailResponse, TraceListResponse, TraceResponse, SpanResponse
from app.services import trace as trace_service

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])


@router.get("", response_model=TraceListResponse)
async def list_traces(
    session_id: uuid.UUID | None = Query(None, description="按 Session 筛选"),
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    workflow_name: str | None = Query(None, description="按 Workflow 筛选"),
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> TraceListResponse:
    """获取 Trace 列表。"""
    traces, total = await trace_service.list_traces(
        db,
        session_id=session_id,
        agent_name=agent_name,
        workflow_name=workflow_name,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    items = [TraceResponse.model_validate(t) for t in traces]
    return TraceListResponse(items=items, total=total)


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> TraceDetailResponse:
    """获取 Trace 详情（含所有 Span 树）。"""
    trace, spans = await trace_service.get_trace_detail(db, trace_id)
    return TraceDetailResponse(
        trace=TraceResponse.model_validate(trace),
        spans=[SpanResponse.model_validate(s) for s in spans],
    )
