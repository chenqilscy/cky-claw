"""Token 审计业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsageLog
from app.schemas.token_usage import (
    SummaryGroupBy,
    TokenUsageByModelItem,
    TokenUsageByUserItem,
    TokenUsageSummaryItem,
)


async def create_token_usage_logs(
    db: AsyncSession,
    logs: list[TokenUsageLog],
) -> None:
    """批量写入 Token 消耗记录。"""
    if not logs:
        return
    db.add_all(logs)
    await db.commit()


def _apply_common_filters(
    stmt,  # type: ignore[no-untyped-def]
    *,
    agent_name: str | None = None,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    model: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):  # type: ignore[no-untyped-def]
    """应用通用筛选条件。"""
    if agent_name:
        stmt = stmt.where(TokenUsageLog.agent_name == agent_name)
    if session_id:
        stmt = stmt.where(TokenUsageLog.session_id == session_id)
    if user_id:
        stmt = stmt.where(TokenUsageLog.user_id == user_id)
    if model:
        stmt = stmt.where(TokenUsageLog.model == model)
    if start_time:
        stmt = stmt.where(TokenUsageLog.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(TokenUsageLog.timestamp <= end_time)
    return stmt


async def list_token_usage(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    model: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TokenUsageLog], int]:
    """查询 Token 消耗记录（分页 + 筛选）。"""
    base = select(TokenUsageLog)
    base = _apply_common_filters(
        base, agent_name=agent_name, session_id=session_id,
        user_id=user_id, model=model, start_time=start_time, end_time=end_time,
    )

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
    model: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    group_by: SummaryGroupBy = SummaryGroupBy.agent_model,
) -> list[TokenUsageSummaryItem | TokenUsageByUserItem | TokenUsageByModelItem]:
    """按指定维度汇总 Token 消耗。"""
    agg_columns = [
        func.sum(TokenUsageLog.prompt_tokens).label("total_prompt_tokens"),
        func.sum(TokenUsageLog.completion_tokens).label("total_completion_tokens"),
        func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
        func.count().label("call_count"),
    ]

    if group_by == SummaryGroupBy.user:
        group_cols = [TokenUsageLog.user_id]
    elif group_by == SummaryGroupBy.model:
        group_cols = [TokenUsageLog.model]
    else:
        group_cols = [TokenUsageLog.agent_name, TokenUsageLog.model]

    base = select(*group_cols, *agg_columns)
    base = _apply_common_filters(
        base, agent_name=agent_name, user_id=user_id,
        model=model, start_time=start_time, end_time=end_time,
    )

    stmt = base.group_by(*group_cols)
    rows = (await db.execute(stmt)).all()

    if group_by == SummaryGroupBy.user:
        return [
            TokenUsageByUserItem(
                user_id=row.user_id,
                total_prompt_tokens=row.total_prompt_tokens,
                total_completion_tokens=row.total_completion_tokens,
                total_tokens=row.total_tokens,
                call_count=row.call_count,
            )
            for row in rows
        ]

    if group_by == SummaryGroupBy.model:
        return [
            TokenUsageByModelItem(
                model=row.model,
                total_prompt_tokens=row.total_prompt_tokens,
                total_completion_tokens=row.total_completion_tokens,
                total_tokens=row.total_tokens,
                call_count=row.call_count,
            )
            for row in rows
        ]

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
