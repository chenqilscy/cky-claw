"""Tool Group 配置业务逻辑层。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.tool_group import ToolGroupConfig
from app.schemas.tool_group import ToolGroupCreate, ToolGroupUpdate


async def list_tool_groups(
    db: AsyncSession,
    *,
    is_enabled: bool | None = None,
) -> tuple[list[ToolGroupConfig], int]:
    """获取工具组列表。"""
    base = select(ToolGroupConfig)
    if is_enabled is not None:
        base = base.where(ToolGroupConfig.is_enabled == is_enabled)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(ToolGroupConfig.created_at.desc())
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_tool_group_by_name(db: AsyncSession, name: str) -> ToolGroupConfig:
    """按 name 获取工具组，不存在则 404。"""
    stmt = select(ToolGroupConfig).where(ToolGroupConfig.name == name)
    tg = (await db.execute(stmt)).scalar_one_or_none()
    if tg is None:
        raise NotFoundError(f"工具组 '{name}' 不存在")
    return tg


async def create_tool_group(db: AsyncSession, data: ToolGroupCreate) -> ToolGroupConfig:
    """创建工具组配置。名称冲突返回 409。"""
    exists_stmt = select(ToolGroupConfig.id).where(ToolGroupConfig.name == data.name)
    existing = (await db.execute(exists_stmt)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"工具组名称 '{data.name}' 已存在")

    tg = ToolGroupConfig(
        name=data.name,
        description=data.description,
        tools=[t.model_dump() for t in data.tools],
        source="custom",
    )
    db.add(tg)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"工具组名称 '{data.name}' 已存在")

    await db.commit()
    await db.refresh(tg)
    return tg


async def update_tool_group(
    db: AsyncSession, name: str, data: ToolGroupUpdate
) -> ToolGroupConfig:
    """更新工具组配置（PATCH 语义）。"""
    tg = await get_tool_group_by_name(db, name)

    if data.description is not None:
        tg.description = data.description
    if data.tools is not None:
        tg.tools = [t.model_dump() for t in data.tools]
    if data.is_enabled is not None:
        tg.is_enabled = data.is_enabled

    tg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tg)
    return tg


async def delete_tool_group(db: AsyncSession, name: str) -> None:
    """删除工具组配置。"""
    tg = await get_tool_group_by_name(db, name)
    await db.delete(tg)
    await db.commit()
