"""Token 审计 API 路由。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.token_usage import (
    TokenUsageListResponse,
    TokenUsageLogResponse,
    TokenUsageSummaryResponse,
)
from app.services import token_usage as token_usage_service

router = APIRouter(prefix="/api/v1/token-usage", tags=["token-usage"])


@router.get("", response_model=TokenUsageListResponse)
async def list_token_usage(
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    session_id: uuid.UUID | None = Query(None, description="按会话 ID 筛选"),
    user_id: uuid.UUID | None = Query(None, description="按用户 ID 筛选"),
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


@router.get("/summary", response_model=TokenUsageSummaryResponse)
async def get_token_usage_summary(
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    user_id: uuid.UUID | None = Query(None, description="按用户 ID 筛选"),
    start_time: datetime | None = Query(None, description="起始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
) -> TokenUsageSummaryResponse:
    """按 Agent + 模型汇总 Token 消耗。"""
    items = await token_usage_service.get_token_usage_summary(
        db,
        agent_name=agent_name,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
    )
    return TokenUsageSummaryResponse(data=items)
