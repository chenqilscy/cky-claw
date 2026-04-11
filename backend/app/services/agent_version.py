"""Agent 版本管理业务逻辑层。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.agent import AgentConfig
from app.models.agent_version import AgentConfigVersion


def _snapshot_from_agent(agent: AgentConfig) -> dict[str, Any]:
    """从 AgentConfig 实例提取完整快照（不含 id/created_at/updated_at 等元数据）。"""
    return {
        "name": agent.name,
        "description": agent.description,
        "instructions": agent.instructions,
        "model": agent.model,
        "provider_name": agent.provider_name,
        "model_settings": agent.model_settings,
        "tool_groups": list(agent.tool_groups) if agent.tool_groups else [],
        "handoffs": list(agent.handoffs) if agent.handoffs else [],
        "guardrails": agent.guardrails,
        "approval_mode": agent.approval_mode,
        "mcp_servers": list(agent.mcp_servers) if agent.mcp_servers else [],
        "agent_tools": list(agent.agent_tools) if agent.agent_tools else [],
        "skills": list(agent.skills) if agent.skills else [],
        "metadata": agent.metadata_,
        "prompt_variables": agent.prompt_variables or [],
    }


async def _next_version(db: AsyncSession, agent_config_id: uuid.UUID) -> int:
    """获取下一个版本号（当前最大版本 + 1，若无版本记录则返回 1）。"""
    stmt = select(func.max(AgentConfigVersion.version)).where(
        AgentConfigVersion.agent_config_id == agent_config_id
    )
    max_ver = (await db.execute(stmt)).scalar_one_or_none()
    return (max_ver or 0) + 1


async def create_version(
    db: AsyncSession,
    agent_config_id: uuid.UUID,
    snapshot: dict[str, Any],
    *,
    change_summary: str | None = None,
    created_by: uuid.UUID | None = None,
) -> AgentConfigVersion:
    """创建一个新版本记录。"""
    version_num = await _next_version(db, agent_config_id)
    record = AgentConfigVersion(
        agent_config_id=agent_config_id,
        version=version_num,
        snapshot=snapshot,
        change_summary=change_summary,
        created_by=created_by,
    )
    db.add(record)
    await db.flush()
    return record


async def list_versions(
    db: AsyncSession,
    agent_config_id: uuid.UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AgentConfigVersion], int]:
    """获取指定 Agent 的版本列表（按版本号降序）。"""
    base = select(AgentConfigVersion).where(
        AgentConfigVersion.agent_config_id == agent_config_id
    )
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(AgentConfigVersion.version.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def get_version(
    db: AsyncSession,
    agent_config_id: uuid.UUID,
    version: int,
) -> AgentConfigVersion:
    """获取指定版本详情。"""
    stmt = select(AgentConfigVersion).where(
        AgentConfigVersion.agent_config_id == agent_config_id,
        AgentConfigVersion.version == version,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"版本 v{version} 不存在")
    return record


async def rollback_to_version(
    db: AsyncSession,
    agent: AgentConfig,
    version: int,
    *,
    created_by: uuid.UUID | None = None,
    change_summary: str | None = None,
) -> AgentConfigVersion:
    """回滚 Agent 到指定版本：用快照恢复字段 + 创建新版本记录。"""
    target = await get_version(db, agent.id, version)
    snap = target.snapshot

    # 恢复字段
    agent.name = snap.get("name", agent.name)
    agent.description = snap.get("description", agent.description)
    agent.instructions = snap.get("instructions", agent.instructions)
    agent.model = snap.get("model", agent.model)
    agent.model_settings = snap.get("model_settings", agent.model_settings)
    agent.tool_groups = snap.get("tool_groups", agent.tool_groups)
    agent.handoffs = snap.get("handoffs", agent.handoffs)
    agent.guardrails = snap.get("guardrails", agent.guardrails)
    agent.approval_mode = snap.get("approval_mode", agent.approval_mode)
    agent.mcp_servers = snap.get("mcp_servers", agent.mcp_servers)
    agent.agent_tools = snap.get("agent_tools", agent.agent_tools)
    agent.skills = snap.get("skills", agent.skills)
    agent.metadata_ = snap.get("metadata", agent.metadata_)
    agent.updated_at = datetime.now(timezone.utc)

    summary = change_summary or f"回滚至 v{version}"
    new_version = await create_version(
        db,
        agent.id,
        snapshot=_snapshot_from_agent(agent),
        change_summary=summary,
        created_by=created_by,
    )
    await db.commit()
    await db.refresh(agent)
    await db.refresh(new_version)
    return new_version


async def get_agent_by_id(db: AsyncSession, agent_id: uuid.UUID) -> AgentConfig:
    """按 ID 获取 Agent，不存在则 404。"""
    stmt = select(AgentConfig).where(
        AgentConfig.id == agent_id, AgentConfig.is_active == True  # noqa: E712
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent '{agent_id}' 不存在")
    return agent
