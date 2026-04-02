"""Agent 配置业务逻辑层。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent import AgentConfig
from app.schemas.agent import AgentCreate, AgentUpdate


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
) -> tuple[list[AgentConfig], int]:
    """获取 Agent 列表（分页 + 可选模糊搜索）。"""
    base = select(AgentConfig).where(AgentConfig.is_active == is_active)
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
    stmt = select(AgentConfig).where(AgentConfig.name == name, AgentConfig.is_active == True)  # noqa: E712
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
        model_settings=data.model_settings,
        tool_groups=data.tool_groups,
        handoffs=data.handoffs,
        guardrails=data.guardrails.model_dump(),
        approval_mode=data.approval_mode,
        mcp_servers=data.mcp_servers,
        skills=data.skills,
        metadata_=data.metadata,
    )
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Agent 名称 '{data.name}' 已存在")
    await db.refresh(agent)
    return agent


async def update_agent(db: AsyncSession, name: str, data: AgentUpdate) -> AgentConfig:
    """更新 Agent 配置（PATCH 语义）。"""
    agent = await get_agent_by_name(db, name)

    update_data = data.model_dump(exclude_unset=True)
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
    """软删除 Agent（is_active = False）。"""
    agent = await get_agent_by_name(db, name)
    agent.is_active = False
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
