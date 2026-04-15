"""A2A 协议业务逻辑层。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models.a2a import A2AAgentCardRecord, A2ATaskRecord

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.a2a import A2AAgentCardCreate, A2AAgentCardUpdate, A2ATaskCreate


# ---------------------------------------------------------------------------
# Agent Card CRUD
# ---------------------------------------------------------------------------
async def create_agent_card(
    db: AsyncSession,
    data: A2AAgentCardCreate,
    *,
    org_id: uuid.UUID | None = None,
) -> A2AAgentCardRecord:
    """创建 Agent Card。"""
    record = A2AAgentCardRecord(
        agent_id=data.agent_id,
        name=data.name,
        description=data.description,
        url=data.url,
        version=data.version,
        capabilities=data.capabilities,
        skills=data.skills,
        authentication=data.authentication,
        metadata_=data.metadata,
        org_id=org_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_agent_card(
    db: AsyncSession,
    card_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> A2AAgentCardRecord:
    """获取 Agent Card。"""
    stmt = select(A2AAgentCardRecord).where(
        A2AAgentCardRecord.id == card_id,
        A2AAgentCardRecord.is_deleted == False,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where(A2AAgentCardRecord.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Agent Card '{card_id}' 不存在")
    return row


async def list_agent_cards(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[A2AAgentCardRecord], int]:
    """分页查询 Agent Card。"""
    base = select(A2AAgentCardRecord).where(A2AAgentCardRecord.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(A2AAgentCardRecord.org_id == org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(A2AAgentCardRecord.updated_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def update_agent_card(
    db: AsyncSession,
    card_id: uuid.UUID,
    data: A2AAgentCardUpdate,
    *,
    org_id: uuid.UUID | None = None,
) -> A2AAgentCardRecord:
    """更新 Agent Card。"""
    row = await get_agent_card(db, card_id, org_id=org_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "metadata":
            row.metadata_ = value
        else:
            setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_agent_card(
    db: AsyncSession,
    card_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> None:
    """软删除 Agent Card。"""
    row = await get_agent_card(db, card_id, org_id=org_id)
    now = datetime.now(UTC)
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    await db.commit()


async def discover_agent_card(
    db: AsyncSession,
    agent_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> A2AAgentCardRecord:
    """通过 Agent ID 发现 Agent Card（服务发现）。"""
    stmt = select(A2AAgentCardRecord).where(
        A2AAgentCardRecord.agent_id == agent_id,
        A2AAgentCardRecord.is_deleted == False,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where(A2AAgentCardRecord.org_id == org_id)
    stmt = stmt.order_by(A2AAgentCardRecord.updated_at.desc()).limit(1)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Agent '{agent_id}' 未发布 Agent Card")
    return row


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------
async def create_task(
    db: AsyncSession,
    data: A2ATaskCreate,
    *,
    org_id: uuid.UUID | None = None,
) -> A2ATaskRecord:
    """创建 A2A Task。"""
    now = datetime.now(UTC)
    record = A2ATaskRecord(
        agent_card_id=data.agent_card_id,
        status="submitted",
        input_messages=data.input_messages,
        artifacts=[],
        history=[{"status": "submitted", "timestamp": now.isoformat(), "message": "任务创建"}],
        metadata_=data.metadata,
        org_id=org_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> A2ATaskRecord:
    """获取 A2A Task。"""
    stmt = select(A2ATaskRecord).where(
        A2ATaskRecord.id == task_id,
        A2ATaskRecord.is_deleted == False,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where(A2ATaskRecord.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"A2A Task '{task_id}' 不存在")
    return row


async def list_tasks(
    db: AsyncSession,
    *,
    agent_card_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[A2ATaskRecord], int]:
    """分页查询 A2A Task。"""
    base = select(A2ATaskRecord).where(A2ATaskRecord.is_deleted == False)  # noqa: E712
    if agent_card_id is not None:
        base = base.where(A2ATaskRecord.agent_card_id == agent_card_id)
    if org_id is not None:
        base = base.where(A2ATaskRecord.org_id == org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(A2ATaskRecord.updated_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def cancel_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> A2ATaskRecord:
    """取消 A2A Task。"""
    row = await get_task(db, task_id, org_id=org_id)
    if row.status in ("completed", "failed", "canceled"):
        raise ValueError(f"任务已处于终态 '{row.status}'，不可取消")
    now = datetime.now(UTC)
    row.status = "canceled"
    history = list(row.history or [])
    history.append({"status": "canceled", "timestamp": now.isoformat(), "message": "用户取消"})
    row.history = history
    row.updated_at = now
    await db.commit()
    await db.refresh(row)
    return row
