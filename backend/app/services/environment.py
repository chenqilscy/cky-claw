"""多环境管理业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent import AgentConfig
from app.models.agent_version import AgentConfigVersion
from app.models.environment import AgentEnvironmentBinding, Environment
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from app.services.audit_log import create_audit_log


async def list_environments(db: AsyncSession, org_id: uuid.UUID | None) -> list[Environment]:
    """按排序字段列出环境。"""
    stmt = select(Environment).order_by(Environment.sort_order.asc(), Environment.name.asc())
    if org_id is not None:
        stmt = stmt.where((Environment.org_id == org_id) | (Environment.org_id.is_(None)))
    return list((await db.execute(stmt)).scalars().all())


async def get_environment_by_name(db: AsyncSession, name: str, org_id: uuid.UUID | None) -> Environment:
    """按名称获取环境。"""
    stmt = select(Environment).where(Environment.name == name)
    if org_id is not None:
        stmt = stmt.where((Environment.org_id == org_id) | (Environment.org_id.is_(None)))
    env = (await db.execute(stmt)).scalar_one_or_none()
    if env is None:
        raise NotFoundError(f"环境 '{name}' 不存在")
    return env


async def create_environment(db: AsyncSession, data: EnvironmentCreate, org_id: uuid.UUID | None) -> Environment:
    """创建环境。"""
    exists = (await db.execute(select(Environment.id).where(Environment.name == data.name))).scalar_one_or_none()
    if exists is not None:
        raise ConflictError(f"环境 '{data.name}' 已存在")

    env = Environment(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        color=data.color,
        sort_order=data.sort_order,
        is_protected=data.is_protected,
        settings_override=data.settings_override,
        org_id=org_id,
    )
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


async def update_environment(
    db: AsyncSession,
    name: str,
    data: EnvironmentUpdate,
    org_id: uuid.UUID | None,
) -> Environment:
    """更新环境。"""
    env = await get_environment_by_name(db, name, org_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(env, key, value)
    env.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(env)
    return env


async def delete_environment(db: AsyncSession, name: str, org_id: uuid.UUID | None) -> None:
    """删除环境（受保护环境不可删）。"""
    env = await get_environment_by_name(db, name, org_id)
    if env.is_protected:
        raise ConflictError(f"环境 '{name}' 为受保护环境，无法删除")
    await db.delete(env)
    await db.commit()


async def _get_agent(db: AsyncSession, agent_name: str, org_id: uuid.UUID | None) -> AgentConfig:
    stmt = select(AgentConfig).where(AgentConfig.name == agent_name, AgentConfig.is_deleted == False)  # noqa: E712
    if org_id is not None:
        stmt = stmt.where((AgentConfig.org_id == org_id) | (AgentConfig.org_id.is_(None)))
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent '{agent_name}' 不存在")
    return agent


async def _latest_version_id(db: AsyncSession, agent_id: uuid.UUID) -> uuid.UUID:
    stmt = (
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_config_id == agent_id)
        .order_by(AgentConfigVersion.version.desc())
        .limit(1)
    )
    ver = (await db.execute(stmt)).scalar_one_or_none()
    if ver is None:
        raise NotFoundError("Agent 尚无可发布版本")
    return ver.id


async def publish_agent(
    db: AsyncSession,
    env_name: str,
    agent_name: str,
    version_id: uuid.UUID | None,
    notes: str,
    org_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> AgentEnvironmentBinding:
    """发布 Agent 到指定环境。"""
    env = await get_environment_by_name(db, env_name, org_id)
    agent = await _get_agent(db, agent_name, org_id)
    target_version_id = version_id or await _latest_version_id(db, agent.id)

    ver_stmt = select(AgentConfigVersion).where(
        AgentConfigVersion.id == target_version_id,
        AgentConfigVersion.agent_config_id == agent.id,
    )
    if (await db.execute(ver_stmt)).scalar_one_or_none() is None:
        raise NotFoundError("目标版本不存在")

    stmt = select(AgentEnvironmentBinding).where(
        AgentEnvironmentBinding.agent_config_id == agent.id,
        AgentEnvironmentBinding.environment_id == env.id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    rollback_from_id: uuid.UUID | None = None
    if existing is not None:
        rollback_from_id = existing.id
        existing.version_id = target_version_id
        existing.published_at = datetime.now(timezone.utc)
        existing.published_by = user_id
        existing.notes = notes
        existing.rollback_from_id = rollback_from_id
        binding = existing
    else:
        binding = AgentEnvironmentBinding(
            agent_config_id=agent.id,
            environment_id=env.id,
            version_id=target_version_id,
            published_by=user_id,
            notes=notes,
            rollback_from_id=None,
            org_id=org_id,
        )
        db.add(binding)

    await db.commit()
    await db.refresh(binding)

    await create_audit_log(
        db,
        user_id=str(user_id) if user_id else None,
        action="environment.publish",
        resource_type="agent_environment_binding",
        resource_id=str(binding.id),
        detail={
            "agent_name": agent_name,
            "environment": env_name,
            "version_id": str(target_version_id),
            "notes": notes,
        },
    )
    return binding


async def rollback_agent(
    db: AsyncSession,
    env_name: str,
    agent_name: str,
    target_version_id: uuid.UUID | None,
    notes: str,
    org_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> AgentEnvironmentBinding:
    """回滚环境中的 Agent 版本。"""
    env = await get_environment_by_name(db, env_name, org_id)
    agent = await _get_agent(db, agent_name, org_id)

    stmt = select(AgentEnvironmentBinding).where(
        AgentEnvironmentBinding.agent_config_id == agent.id,
        AgentEnvironmentBinding.environment_id == env.id,
    )
    binding = (await db.execute(stmt)).scalar_one_or_none()
    if binding is None:
        raise NotFoundError("当前环境未发布该 Agent")

    if target_version_id is None:
        versions = (
            await db.execute(
                select(AgentConfigVersion)
                .where(AgentConfigVersion.agent_config_id == agent.id)
                .order_by(AgentConfigVersion.version.desc())
                .limit(2)
            )
        ).scalars().all()
        if len(versions) < 2:
            raise NotFoundError("没有可回滚的历史版本")
        target_version_id = versions[1].id

    ver_stmt = select(AgentConfigVersion).where(
        AgentConfigVersion.id == target_version_id,
        AgentConfigVersion.agent_config_id == agent.id,
    )
    if (await db.execute(ver_stmt)).scalar_one_or_none() is None:
        raise NotFoundError("目标版本不存在")

    old_binding_id = binding.id
    binding.version_id = target_version_id
    binding.published_at = datetime.now(timezone.utc)
    binding.published_by = user_id
    binding.notes = notes
    binding.rollback_from_id = old_binding_id

    await db.commit()
    await db.refresh(binding)

    await create_audit_log(
        db,
        user_id=str(user_id) if user_id else None,
        action="environment.rollback",
        resource_type="agent_environment_binding",
        resource_id=str(binding.id),
        detail={
            "agent_name": agent_name,
            "environment": env_name,
            "target_version_id": str(target_version_id),
            "notes": notes,
        },
    )
    return binding


async def list_environment_agents(
    db: AsyncSession,
    env_name: str,
    org_id: uuid.UUID | None,
) -> list[AgentEnvironmentBinding]:
    """列出环境内已发布的 Agent 绑定。"""
    env = await get_environment_by_name(db, env_name, org_id)
    stmt = select(AgentEnvironmentBinding).where(
        AgentEnvironmentBinding.environment_id == env.id,
        AgentEnvironmentBinding.is_active == True,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where((AgentEnvironmentBinding.org_id == org_id) | (AgentEnvironmentBinding.org_id.is_(None)))
    return list((await db.execute(stmt)).scalars().all())


async def diff_environments(
    db: AsyncSession,
    agent_name: str,
    env1: str,
    env2: str,
    org_id: uuid.UUID | None,
) -> tuple[dict, dict]:
    """对比两个环境中同一 Agent 的发布快照。"""
    agent = await _get_agent(db, agent_name, org_id)
    env_obj1 = await get_environment_by_name(db, env1, org_id)
    env_obj2 = await get_environment_by_name(db, env2, org_id)

    b1 = (
        await db.execute(
            select(AgentEnvironmentBinding).where(
                and_(
                    AgentEnvironmentBinding.agent_config_id == agent.id,
                    AgentEnvironmentBinding.environment_id == env_obj1.id,
                )
            )
        )
    ).scalar_one_or_none()
    b2 = (
        await db.execute(
            select(AgentEnvironmentBinding).where(
                and_(
                    AgentEnvironmentBinding.agent_config_id == agent.id,
                    AgentEnvironmentBinding.environment_id == env_obj2.id,
                )
            )
        )
    ).scalar_one_or_none()
    if b1 is None or b2 is None:
        raise NotFoundError("指定环境中未找到该 Agent 的发布记录")

    v1 = (await db.execute(select(AgentConfigVersion).where(AgentConfigVersion.id == b1.version_id))).scalar_one()
    v2 = (await db.execute(select(AgentConfigVersion).where(AgentConfigVersion.id == b2.version_id))).scalar_one()
    return v1.snapshot, v2.snapshot
