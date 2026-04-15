"""Agent 多语言 Instructions 业务逻辑层。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.agent import AgentConfig
from app.models.agent_locale import AgentLocale

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.agent_locale import AgentLocaleCreate, AgentLocaleUpdate


async def _get_agent_id_by_name(db: AsyncSession, name: str) -> uuid.UUID:
    """按 name 获取 Agent ID。不存在则 404。"""
    stmt = select(AgentConfig.id).where(
        AgentConfig.name == name,
        AgentConfig.is_active == True,  # noqa: E712
        AgentConfig.is_deleted == False,  # noqa: E712
    )
    agent_id = (await db.execute(stmt)).scalar_one_or_none()
    if agent_id is None:
        raise NotFoundError(f"Agent '{name}' 不存在")
    return agent_id


async def list_locales(db: AsyncSession, agent_name: str) -> list[AgentLocale]:
    """获取 Agent 的全部语言版本。"""
    agent_id = await _get_agent_id_by_name(db, agent_name)
    stmt = (
        select(AgentLocale)
        .where(AgentLocale.agent_id == agent_id)
        .order_by(AgentLocale.is_default.desc(), AgentLocale.locale)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def create_locale(
    db: AsyncSession, agent_name: str, data: AgentLocaleCreate
) -> AgentLocale:
    """为 Agent 新增语言版本。locale 重复返回 409。"""
    agent_id = await _get_agent_id_by_name(db, agent_name)

    # 检查 locale 是否已存在
    exists_stmt = select(AgentLocale.id).where(
        AgentLocale.agent_id == agent_id,
        AgentLocale.locale == data.locale,
    )
    if (await db.execute(exists_stmt)).scalar_one_or_none() is not None:
        raise ConflictError(f"Agent '{agent_name}' 的 locale '{data.locale}' 已存在")

    # 如果设为默认，先取消旧默认
    if data.is_default:
        await _clear_default(db, agent_id)

    locale_record = AgentLocale(
        agent_id=agent_id,
        locale=data.locale,
        instructions=data.instructions,
        is_default=data.is_default,
    )
    db.add(locale_record)
    await db.commit()
    await db.refresh(locale_record)
    return locale_record


async def update_locale(
    db: AsyncSession, agent_name: str, locale: str, data: AgentLocaleUpdate
) -> AgentLocale:
    """更新指定语言版本的 Instructions。"""
    agent_id = await _get_agent_id_by_name(db, agent_name)
    record = await _get_locale_record(db, agent_id, locale)

    record.instructions = data.instructions
    record.updated_at = datetime.now(UTC)

    if data.is_default is True:
        await _clear_default(db, agent_id)
        record.is_default = True
    elif data.is_default is False:
        if record.is_default:
            # 不允许取消唯一的默认版本
            other_default = await _has_other_default(db, agent_id, record.id)
            if not other_default:
                raise ValidationError("不可取消唯一的默认语言版本")
        record.is_default = False

    await db.commit()
    await db.refresh(record)
    return record


async def delete_locale(db: AsyncSession, agent_name: str, locale: str) -> None:
    """删除指定语言版本。默认语言版本不可删除。"""
    agent_id = await _get_agent_id_by_name(db, agent_name)
    record = await _get_locale_record(db, agent_id, locale)

    if record.is_default:
        raise ValidationError("默认语言版本不可删除，请先切换默认语言")

    await db.delete(record)
    await db.commit()


async def _get_locale_record(
    db: AsyncSession, agent_id: uuid.UUID, locale: str
) -> AgentLocale:
    """获取单条 locale 记录。不存在则 404。"""
    stmt = select(AgentLocale).where(
        AgentLocale.agent_id == agent_id,
        AgentLocale.locale == locale,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"语言版本 '{locale}' 不存在")
    return record


async def _clear_default(db: AsyncSession, agent_id: uuid.UUID) -> None:
    """取消 Agent 所有语言版本的默认标记。"""
    stmt = (
        update(AgentLocale)
        .where(AgentLocale.agent_id == agent_id, AgentLocale.is_default == True)  # noqa: E712
        .values(is_default=False)
    )
    await db.execute(stmt)


async def _has_other_default(
    db: AsyncSession, agent_id: uuid.UUID, exclude_id: uuid.UUID
) -> bool:
    """检查是否存在其他默认语言版本。"""
    stmt = select(AgentLocale.id).where(
        AgentLocale.agent_id == agent_id,
        AgentLocale.is_default == True,  # noqa: E712
        AgentLocale.id != exclude_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None
