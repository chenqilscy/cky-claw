"""Token 审计业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsageLog
from app.schemas.token_usage import TokenUsageSummaryItem


async def create_token_usage_logs(
    db: AsyncSession,
    logs: list[TokenUsageLog],
) -> None:
    """批量写入 Token 消耗记录。"""
    if not logs:
        return
    db.add_all(logs)
    await db.commit()


async def list_token_usage(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TokenUsageLog], int]:
    """查询 Token 消耗记录（分页 + 筛选）。"""
    base = select(TokenUsageLog)

    if agent_name:
        base = base.where(TokenUsageLog.agent_name == agent_name)
    if session_id:
        base = base.where(TokenUsageLog.session_id == session_id)
    if user_id:
        base = base.where(TokenUsageLog.user_id == user_id)
    if start_time:
        base = base.where(TokenUsageLog.timestamp >= start_time)
    if end_time:
        base = base.where(TokenUsageLog.timestamp <= end_time)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(TokenUsageLog.timestamp.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_token_usage_summary(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    user_id: uuid.UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[TokenUsageSummaryItem]:
    """按 agent_name + model 汇总 Token 消耗。"""
    base = select(
        TokenUsageLog.agent_name,
        TokenUsageLog.model,
        func.sum(TokenUsageLog.prompt_tokens).label("total_prompt_tokens"),
        func.sum(TokenUsageLog.completion_tokens).label("total_completion_tokens"),
        func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
        func.count().label("call_count"),
    )

    if agent_name:
        base = base.where(TokenUsageLog.agent_name == agent_name)
    if user_id:
        base = base.where(TokenUsageLog.user_id == user_id)
    if start_time:
        base = base.where(TokenUsageLog.timestamp >= start_time)
    if end_time:
        base = base.where(TokenUsageLog.timestamp <= end_time)

    stmt = base.group_by(TokenUsageLog.agent_name, TokenUsageLog.model)
    rows = (await db.execute(stmt)).all()

    return [
        TokenUsageSummaryItem(
            agent_name=row.agent_name,
            model=row.model,
            total_prompt_tokens=row.total_prompt_tokens,
            total_completion_tokens=row.total_completion_tokens,
            total_tokens=row.total_tokens,
            call_count=row.call_count,
        )
        for row in rows
    ]
