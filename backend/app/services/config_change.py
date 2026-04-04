"""配置变更审计服务 — CRUD + 回滚 + 历史查询。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_change_log import ConfigChangeLog
from app.schemas.config_change_log import ConfigChangeLogCreate


async def record_change(
    db: AsyncSession,
    data: ConfigChangeLogCreate,
    *,
    changed_by: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
) -> ConfigChangeLog:
    """记录一条配置变更日志。"""
    log = ConfigChangeLog(
        config_key=data.config_key,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        old_value=data.old_value,
        new_value=data.new_value,
        changed_by=changed_by,
        change_source=data.change_source,
        description=data.description,
        org_id=org_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_change_logs(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    config_key: str | None = None,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[ConfigChangeLog], int]:
    """分页查询配置变更日志。"""
    q = select(ConfigChangeLog)
    if entity_type is not None:
        q = q.where(ConfigChangeLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(ConfigChangeLog.entity_id == entity_id)
    if config_key is not None:
        q = q.where(ConfigChangeLog.config_key == config_key)
    if org_id is not None:
        q = q.where(ConfigChangeLog.org_id == org_id)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0
    result = await db.execute(q.order_by(ConfigChangeLog.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_change_log(
    db: AsyncSession,
    change_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> ConfigChangeLog | None:
    """按 ID 查询变更日志。传入 org_id 时强制租户隔离。"""
    q = select(ConfigChangeLog).where(ConfigChangeLog.id == change_id)
    if org_id is not None:
        q = q.where(ConfigChangeLog.org_id == org_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def rollback_change(
    db: AsyncSession,
    change: ConfigChangeLog,
    *,
    changed_by: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
) -> ConfigChangeLog:
    """回滚指定变更 — 创建一条反向变更日志。

    注意：回滚仅记录审计日志，实际配置恢复由调用方（API 层）完成。
    """
    rollback_log = ConfigChangeLog(
        config_key=change.config_key,
        entity_type=change.entity_type,
        entity_id=change.entity_id,
        old_value=change.new_value,
        new_value=change.old_value,
        changed_by=changed_by,
        change_source="rollback",
        rollback_ref=change.id,
        description=f"回滚变更 {change.id}",
        org_id=org_id,
    )
    db.add(rollback_log)
    await db.commit()
    await db.refresh(rollback_log)
    return rollback_log
