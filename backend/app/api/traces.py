"""Trace 查询 API。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_db, require_permission
from app.core.tenant import get_org_id
from app.schemas.trace import (
    SpanListResponse,
    SpanResponse,
    TraceDetailResponse,
    TraceListResponse,
    TraceResponse,
    TraceStatsResponse,
)
from app.services import trace as trace_service

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])


@router.get("/stats", response_model=TraceStatsResponse, dependencies=[Depends(require_permission("traces", "read"))])
async def get_trace_stats(
    session_id: uuid.UUID | None = Query(None, description="按 Session 筛选"),
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    start_time: datetime | None = Query(None, description="起始时间（默认最近 7 天）"),
    end_time: datetime | None = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> TraceStatsResponse:
    """获取 Trace 统计数据（支持租户隔离）。"""
    stats = await trace_service.get_trace_stats(
        db,
        session_id=session_id,
        agent_name=agent_name,
        start_time=start_time,
        end_time=end_time,
        org_id=org_id,
    )
    return TraceStatsResponse(**stats)


@router.get("/spans", response_model=SpanListResponse, dependencies=[Depends(require_permission("traces", "read"))])
async def list_spans(
    trace_id: str | None = Query(None, description="按 Trace 筛选"),
    type: str | None = Query(None, description="Span 类型: agent/llm/tool/handoff/guardrail"),
    status: str | None = Query(None, description="Span 状态: completed/failed/cancelled"),
    name: str | None = Query(None, description="按名称模糊搜索"),
    min_duration_ms: int | None = Query(None, ge=0, description="最小耗时（毫秒）"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> SpanListResponse:
    """搜索 Span。"""
    spans, total = await trace_service.list_spans(
        db,
        trace_id=trace_id,
        type=type,
        status=status,
        name=name,
        min_duration_ms=min_duration_ms,
        limit=limit,
        offset=offset,
    )
    items = [SpanResponse.model_validate(s) for s in spans]
    return SpanListResponse(data=items, total=total, limit=limit, offset=offset)


@router.get("", response_model=TraceListResponse, dependencies=[Depends(require_permission("traces", "read"))])
async def list_traces(
    session_id: uuid.UUID | None = Query(None, description="按 Session 筛选"),
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    workflow_name: str | None = Query(None, description="按 Workflow 筛选"),
    status: str | None = Query(None, description="按状态筛选"),
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    min_duration_ms: int | None = Query(None, ge=0, description="最小耗时（毫秒）"),
    max_duration_ms: int | None = Query(None, ge=0, description="最大耗时（毫秒）"),
    has_guardrail_triggered: bool | None = Query(None, description="是否含 Guardrail 触发"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> TraceListResponse:
    """获取 Trace 列表（支持租户隔离）。"""
    traces, total = await trace_service.list_traces(
        db,
        session_id=session_id,
        agent_name=agent_name,
        workflow_name=workflow_name,
        status=status,
        start_time=start_time,
        end_time=end_time,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        has_guardrail_triggered=has_guardrail_triggered,
        org_id=org_id,
        limit=limit,
        offset=offset,
    )
    items = [TraceResponse.model_validate(t) for t in traces]
    return TraceListResponse(data=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{trace_id}",
    response_model=TraceDetailResponse,
    dependencies=[Depends(require_permission("traces", "read"))],
)
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


@router.get(
    "/{trace_id}/flame",
    dependencies=[Depends(require_permission("traces", "read"))],
)
async def get_trace_flame(
    trace_id: str,
    max_depth: int = Query(50, ge=1, le=100, description="最大嵌套深度"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取 Trace 火焰图树结构（嵌套 parent→children）。"""
    return await trace_service.build_flame_tree(db, trace_id, max_depth=max_depth)


@router.get(
    "/{trace_id}/replay",
    dependencies=[Depends(require_permission("traces", "read"))],
)
async def get_trace_replay(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取 Trace 回放时间轴 — 按时间顺序排列的 Span 事件序列。"""
    return await trace_service.build_replay_timeline(db, trace_id)
