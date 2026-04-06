"""Token 审计 API 路由。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.schemas.token_usage import (
    SummaryGroupBy,
    TokenUsageListResponse,
    TokenUsageLogResponse,
    TokenUsageSummaryResponse,
    TokenUsageTrendResponse,
)
from app.services import token_usage as token_usage_service

router = APIRouter(prefix="/api/v1/token-usage", tags=["token-usage"])


@router.get("", response_model=TokenUsageListResponse, dependencies=[Depends(require_permission("token_usage", "read"))])
async def list_token_usage(
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    session_id: uuid.UUID | None = Query(None, description="按会话 ID 筛选"),
    user_id: uuid.UUID | None = Query(None, description="按用户 ID 筛选"),
    model: str | None = Query(None, description="按模型筛选"),
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> TokenUsageListResponse:
    """查询 Token 消耗记录。"""
    logs, total = await token_usage_service.list_token_usage(
        db,
        agent_name=agent_name,
        session_id=session_id,
        user_id=user_id,
        model=model,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return TokenUsageListResponse(
        data=[TokenUsageLogResponse.model_validate(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=TokenUsageSummaryResponse, dependencies=[Depends(require_permission("token_usage", "read"))])
async def get_token_usage_summary(
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    user_id: uuid.UUID | None = Query(None, description="按用户 ID 筛选"),
    model: str | None = Query(None, description="按模型筛选"),
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    group_by: SummaryGroupBy = Query(SummaryGroupBy.agent_model, description="汇总维度"),
    db: AsyncSession = Depends(get_db),
) -> TokenUsageSummaryResponse:
    """按指定维度汇总 Token 消耗。"""
    items = await token_usage_service.get_token_usage_summary(
        db,
        agent_name=agent_name,
        user_id=user_id,
        model=model,
        start_time=start_time,
        end_time=end_time,
        group_by=group_by,
    )
    return TokenUsageSummaryResponse(data=items)


@router.get("/trend", response_model=TokenUsageTrendResponse, dependencies=[Depends(require_permission("token_usage", "read"))])
async def get_token_usage_trend(
    days: int = Query(7, ge=1, le=90, description="最近天数"),
    group_by_model: bool = Query(False, description="是否按模型分组"),
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    db: AsyncSession = Depends(get_db),
) -> TokenUsageTrendResponse:
    """查询 Token 消耗趋势（按日聚合）。"""
    items = await token_usage_service.get_token_usage_trend(
        db,
        days=days,
        group_by_model=group_by_model,
        agent_name=agent_name,
    )
    return TokenUsageTrendResponse(data=items, days=days)
