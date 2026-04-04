"""APM 指标聚合服务层。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, cast, func, select, Float
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsageLog
from app.models.trace import SpanRecord, TraceRecord
from app.schemas.apm import (
    AgentRankItem,
    ApmDashboardResponse,
    ApmOverview,
    DailyTrendItem,
    ModelUsageItem,
    ToolUsageItem,
)


async def get_apm_dashboard(db: AsyncSession, *, days: int = 30) -> ApmDashboardResponse:
    """聚合 APM 仪表盘数据。

    Args:
        db: 数据库会话
        days: 统计范围（天）
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    overview = await _get_overview(db, since)
    agent_ranking = await _get_agent_ranking(db, since)
    model_usage = await _get_model_usage(db, since)
    daily_trend = await _get_daily_trend(db, since)
    tool_usage = await _get_tool_usage(db, since)

    return ApmDashboardResponse(
        overview=overview,
        agent_ranking=agent_ranking,
        model_usage=model_usage,
        daily_trend=daily_trend,
        tool_usage=tool_usage,
    )


async def _get_overview(db: AsyncSession, since: datetime) -> ApmOverview:
    """聚合总览指标。"""
    # Trace 统计
    trace_stmt = select(
        func.count(TraceRecord.id).label("total_traces"),
        func.coalesce(func.avg(TraceRecord.duration_ms), 0).label("avg_duration_ms"),
        func.coalesce(
            func.sum(case((TraceRecord.status == "error", 1), else_=0)),
            0,
        ).label("error_count"),
    ).where(TraceRecord.created_at >= since)
    trace_row = (await db.execute(trace_stmt)).one()

    # Span 统计
    span_count_stmt = select(func.count(SpanRecord.id)).where(SpanRecord.created_at >= since)
    total_spans = (await db.execute(span_count_stmt)).scalar_one()

    # Token 统计
    token_stmt = select(
        func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(TokenUsageLog.total_cost), 0).label("total_cost"),
    ).where(TokenUsageLog.timestamp >= since)
    token_row = (await db.execute(token_stmt)).one()

    total_traces = trace_row.total_traces or 0
    error_count = trace_row.error_count or 0
    error_rate = (error_count / total_traces * 100) if total_traces > 0 else 0.0

    return ApmOverview(
        total_traces=total_traces,
        total_spans=total_spans or 0,
        total_tokens=token_row.total_tokens or 0,
        total_cost=round(float(token_row.total_cost or 0), 4),
        avg_duration_ms=round(float(trace_row.avg_duration_ms or 0), 1),
        error_rate=round(error_rate, 2),
    )


async def _get_agent_ranking(db: AsyncSession, since: datetime) -> list[AgentRankItem]:
    """Agent 调用排名（按调用次数降序，Top 10）。"""
    stmt = (
        select(
            TraceRecord.agent_name,
            func.count(TraceRecord.id).label("call_count"),
            func.coalesce(func.avg(TraceRecord.duration_ms), 0).label("avg_duration_ms"),
            func.coalesce(
                func.sum(case((TraceRecord.status == "error", 1), else_=0)),
                0,
            ).label("error_count"),
        )
        .where(TraceRecord.created_at >= since, TraceRecord.agent_name.isnot(None))
        .group_by(TraceRecord.agent_name)
        .order_by(func.count(TraceRecord.id).desc())
        .limit(10)
    )
    rows = (await db.execute(stmt)).all()

    # 关联 Token 聚合
    agent_names = [r.agent_name for r in rows]
    token_map: dict[str, tuple[int, float]] = {}
    if agent_names:
        token_stmt = (
            select(
                TokenUsageLog.agent_name,
                func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(TokenUsageLog.total_cost), 0).label("total_cost"),
            )
            .where(TokenUsageLog.timestamp >= since, TokenUsageLog.agent_name.in_(agent_names))
            .group_by(TokenUsageLog.agent_name)
        )
        token_rows = (await db.execute(token_stmt)).all()
        for tr in token_rows:
            token_map[tr.agent_name] = (tr.total_tokens or 0, float(tr.total_cost or 0))

    return [
        AgentRankItem(
            agent_name=r.agent_name,
            call_count=r.call_count,
            total_tokens=token_map.get(r.agent_name, (0, 0.0))[0],
            total_cost=round(token_map.get(r.agent_name, (0, 0.0))[1], 4),
            avg_duration_ms=round(float(r.avg_duration_ms), 1),
            error_count=r.error_count,
        )
        for r in rows
    ]


async def _get_model_usage(db: AsyncSession, since: datetime) -> list[ModelUsageItem]:
    """模型使用分布。"""
    stmt = (
        select(
            TokenUsageLog.model,
            func.count(TokenUsageLog.id).label("call_count"),
            func.coalesce(func.sum(TokenUsageLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsageLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsageLog.total_cost), 0).label("total_cost"),
        )
        .where(TokenUsageLog.timestamp >= since, TokenUsageLog.model.isnot(None))
        .group_by(TokenUsageLog.model)
        .order_by(func.sum(TokenUsageLog.total_tokens).desc())
        .limit(10)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ModelUsageItem(
            model=r.model,
            call_count=r.call_count,
            prompt_tokens=r.prompt_tokens or 0,
            completion_tokens=r.completion_tokens or 0,
            total_tokens=r.total_tokens or 0,
            total_cost=round(float(r.total_cost or 0), 4),
        )
        for r in rows
    ]


async def _get_daily_trend(db: AsyncSession, since: datetime) -> list[DailyTrendItem]:
    """每日趋势（Trace 数量 + Token 总量 + 成本）。"""
    # 每日 Trace 数
    trace_stmt = (
        select(
            func.date(TraceRecord.created_at).label("day"),
            func.count(TraceRecord.id).label("traces"),
        )
        .where(TraceRecord.created_at >= since)
        .group_by(func.date(TraceRecord.created_at))
        .order_by(func.date(TraceRecord.created_at))
    )
    trace_rows = (await db.execute(trace_stmt)).all()
    trace_map = {str(r.day): r.traces for r in trace_rows}

    # 每日 Token
    token_stmt = (
        select(
            func.date(TokenUsageLog.timestamp).label("day"),
            func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(TokenUsageLog.total_cost), 0).label("cost"),
        )
        .where(TokenUsageLog.timestamp >= since)
        .group_by(func.date(TokenUsageLog.timestamp))
        .order_by(func.date(TokenUsageLog.timestamp))
    )
    token_rows = (await db.execute(token_stmt)).all()
    token_map = {str(r.day): (r.tokens, float(r.cost)) for r in token_rows}

    # 合并
    all_dates = sorted(set(trace_map.keys()) | set(token_map.keys()))
    return [
        DailyTrendItem(
            date=d,
            traces=trace_map.get(d, 0),
            tokens=token_map.get(d, (0, 0.0))[0],
            cost=round(token_map.get(d, (0, 0.0))[1], 4),
        )
        for d in all_dates
    ]


async def _get_tool_usage(db: AsyncSession, since: datetime) -> list[ToolUsageItem]:
    """工具调用排名（Top 10）。"""
    stmt = (
        select(
            SpanRecord.name,
            func.count(SpanRecord.id).label("call_count"),
            func.coalesce(func.avg(SpanRecord.duration_ms), 0).label("avg_duration_ms"),
        )
        .where(SpanRecord.created_at >= since, SpanRecord.type == "tool")
        .group_by(SpanRecord.name)
        .order_by(func.count(SpanRecord.id).desc())
        .limit(10)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ToolUsageItem(
            tool_name=r.name or "unknown",
            call_count=r.call_count,
            avg_duration_ms=round(float(r.avg_duration_ms), 1),
        )
        for r in rows
    ]
