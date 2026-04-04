"""Team 团队业务逻辑层。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.team import TeamConfig
from app.schemas.team import TeamConfigCreate, TeamConfigUpdate

logger = logging.getLogger(__name__)

_VALID_PROTOCOLS = {"SEQUENTIAL", "PARALLEL", "COORDINATOR"}


async def create_team(db: AsyncSession, data: TeamConfigCreate) -> TeamConfig:
    """创建团队配置。"""
    if data.protocol not in _VALID_PROTOCOLS:
        raise ValueError(f"无效协议 '{data.protocol}'，可选值: {_VALID_PROTOCOLS}")
    if data.protocol == "COORDINATOR" and not data.coordinator_agent_id:
        raise ValueError("COORDINATOR 协议必须指定 coordinator_agent_id")
    record = TeamConfig(
        name=data.name,
        description=data.description,
        protocol=data.protocol,
        member_agent_ids=data.member_agent_ids,
        coordinator_agent_id=data.coordinator_agent_id,
        config=data.config,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"团队名称 '{data.name}' 已存在")
    await db.refresh(record)
    return record


async def get_team(db: AsyncSession, team_id: uuid.UUID) -> TeamConfig:
    """获取单个团队配置。"""
    stmt = select(TeamConfig).where(TeamConfig.id == team_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"团队 '{team_id}' 不存在")
    return record


async def list_teams(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[TeamConfig], int]:
    """查询团队配置列表（分页+搜索）。"""
    base_stmt = select(TeamConfig)
    count_stmt = select(func.count()).select_from(TeamConfig)

    if search:
        pattern = f"%{search}%"
        base_stmt = base_stmt.where(TeamConfig.name.ilike(pattern))
        count_stmt = count_stmt.where(TeamConfig.name.ilike(pattern))

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = base_stmt.order_by(TeamConfig.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def update_team(db: AsyncSession, team_id: uuid.UUID, data: TeamConfigUpdate) -> TeamConfig:
    """更新团队配置（部分更新）。"""
    record = await get_team(db, team_id)
    update_data = data.model_dump(exclude_unset=True)

    if "protocol" in update_data and update_data["protocol"] not in _VALID_PROTOCOLS:
        raise ValueError(f"无效协议 '{update_data['protocol']}'，可选值: {_VALID_PROTOCOLS}")

    for key, value in update_data.items():
        setattr(record, key, value)

    # 更新后再次校验 COORDINATOR 约束
    if record.protocol == "COORDINATOR" and not record.coordinator_agent_id:
        raise ValueError("COORDINATOR 协议必须指定 coordinator_agent_id")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"团队名称 '{data.name}' 已存在")
    await db.refresh(record)
    return record


async def delete_team(db: AsyncSession, team_id: uuid.UUID) -> None:
    """删除团队配置。"""
    record = await get_team(db, team_id)
    await db.delete(record)
    await db.commit()
