"""Agent 配置业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent import AgentConfig
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.agent_version import _snapshot_from_agent, create_version


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_agents(
    db: AsyncSession,
    *,
    search: str | None = None,
    is_active: bool = True,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[AgentConfig], int]:
    """获取 Agent 列表（分页 + 可选模糊搜索）。"""
    base = select(AgentConfig).where(
        AgentConfig.is_active == is_active, AgentConfig.is_deleted == False  # noqa: E712
    )
    if org_id is not None:
        base = base.where(AgentConfig.org_id == org_id)
    if search:
        pattern = f"%{_escape_like(search)}%"
        base = base.where(
            AgentConfig.name.ilike(pattern) | AgentConfig.description.ilike(pattern)
        )

    # 总数
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # 分页数据
    data_stmt = base.order_by(AgentConfig.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_agent_by_name(db: AsyncSession, name: str) -> AgentConfig:
    """按 name 获取 Agent，不存在则 404。"""
    stmt = select(AgentConfig).where(
        AgentConfig.name == name, AgentConfig.is_active == True, AgentConfig.is_deleted == False  # noqa: E712
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent '{name}' 不存在")
    return agent


async def create_agent(db: AsyncSession, data: AgentCreate) -> AgentConfig:
    """创建 Agent 配置。名称冲突返回 409。"""
    # 检查名称冲突（含已软删除的）
    exists_stmt = select(AgentConfig.id).where(AgentConfig.name == data.name)
    existing = (await db.execute(exists_stmt)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Agent 名称 '{data.name}' 已存在")

    agent = AgentConfig(
        name=data.name,
        description=data.description,
        instructions=data.instructions,
        model=data.model,
        provider_name=data.provider_name,
        model_settings=data.model_settings,
        tool_groups=data.tool_groups,
        handoffs=data.handoffs,
        guardrails=data.guardrails.model_dump(),
        approval_mode=data.approval_mode,
        mcp_servers=data.mcp_servers,
        agent_tools=data.agent_tools,
        skills=data.skills,
        output_type=data.output_type,
        metadata_=data.metadata,
        prompt_variables=data.prompt_variables,
    )
    db.add(agent)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Agent 名称 '{data.name}' 已存在")

    # 创建初始版本快照（v1），与 Agent 在同一事务内
    await create_version(
        db,
        agent.id,
        snapshot=_snapshot_from_agent(agent),
        change_summary="初始创建",
    )
    await db.commit()
    await db.refresh(agent)

    return agent


async def update_agent(db: AsyncSession, name: str, data: AgentUpdate) -> AgentConfig:
    """更新 Agent 配置（PATCH 语义）。"""
    agent = await get_agent_by_name(db, name)

    # 更新前自动快照
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        changed_fields = ", ".join(update_data.keys())
        await create_version(
            db,
            agent.id,
            snapshot=_snapshot_from_agent(agent),
            change_summary=f"更新字段: {changed_fields}",
        )

    for field, value in update_data.items():
        if field == "guardrails" and value is not None:
            value = data.guardrails.model_dump()  # type: ignore[union-attr]
        if field == "metadata":
            setattr(agent, "metadata_", value)
        else:
            setattr(agent, field, value)

    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, name: str) -> None:
    """软删除 Agent（is_active = False + is_deleted = True）。"""
    agent = await get_agent_by_name(db, name)
    agent.is_active = False
    agent.is_deleted = True
    agent.deleted_at = datetime.now(timezone.utc)
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()


async def get_agent_realtime_status(
    db: AsyncSession,
    minutes: int = 5,
) -> list[dict[str, Any]]:
    """查询各 Agent 最近 N 分钟的运行状态（基于 Trace 数据聚合）。"""
    from sqlalchemy import case as sa_case

    from app.models.trace import TraceRecord

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    error_count_expr = func.sum(sa_case((TraceRecord.status == "error", 1), else_=0))
    stmt = (
        select(
            TraceRecord.agent_name,
            func.count().label("run_count"),
            func.max(TraceRecord.start_time).label("last_active_at"),
            error_count_expr.label("error_count"),
        )
        .where(TraceRecord.start_time >= cutoff)
        .where(TraceRecord.agent_name.isnot(None))
        .group_by(TraceRecord.agent_name)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    agents: list[dict[str, Any]] = []
    for row in rows:
        agents.append({
            "agent_name": row.agent_name,
            "run_count": row.run_count,
            "last_active_at": row.last_active_at.isoformat() if row.last_active_at else None,
            "error_count": row.error_count or 0,
            "status": "active" if row.run_count > row.error_count else "error",
        })
    return agents


async def get_agent_activity_trend(
    db: AsyncSession,
    hours: int = 1,
    interval_minutes: int = 5,
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """获取 Agent 活动趋势数据（按时间桶聚合，支持租户隔离）。"""
    from sqlalchemy import case as sa_case, text

    from app.models.trace import TraceRecord

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    error_expr = func.sum(sa_case((TraceRecord.status == "error", 1), else_=0))

    # 向下截断到指定时间间隔的桶
    time_bucket = func.to_timestamp(
        func.floor(
            func.extract("epoch", TraceRecord.start_time) / (interval_minutes * 60)
        ) * (interval_minutes * 60)
    ).label("time_bucket")

    stmt = (
        select(
            time_bucket,
            func.count().label("run_count"),
            error_expr.label("error_count"),
        )
        .where(TraceRecord.start_time >= cutoff)
        .where(TraceRecord.agent_name.isnot(None))
    )
    if org_id is not None:
        stmt = stmt.where(TraceRecord.org_id == org_id)
    stmt = stmt.group_by(text("1")).order_by(text("1"))
    result = await db.execute(stmt)
    return [
        {
            "time": row.time_bucket.isoformat() if row.time_bucket else None,
            "run_count": row.run_count,
            "error_count": row.error_count or 0,
        }
        for row in result.all()
    ]
