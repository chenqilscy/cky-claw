"""Memory 记忆条目业务逻辑层。"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select, update

from app.core.exceptions import NotFoundError
from app.models.memory import MemoryEntryRecord
from app.schemas.memory import (
    MemoryCreate,
    MemoryDecayModeEnum,
    MemoryDecayRequest,
    MemorySearchRequest,
    MemoryTagSearchRequest,
    MemoryUpdate,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_memory(db: AsyncSession, data: MemoryCreate) -> MemoryEntryRecord:
    """创建记忆条目。"""
    record = MemoryEntryRecord(
        user_id=data.user_id,
        type=data.type.value,
        content=data.content,
        confidence=data.confidence,
        agent_name=data.agent_name,
        source_session_id=data.source_session_id,
        metadata_=data.metadata,
        embedding=data.embedding,
        tags=data.tags,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_memory(db: AsyncSession, entry_id: uuid.UUID) -> MemoryEntryRecord:
    """获取单条记忆条目。"""
    stmt = select(MemoryEntryRecord).where(
        MemoryEntryRecord.id == entry_id, MemoryEntryRecord.is_deleted == False  # noqa: E712
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"记忆条目 '{entry_id}' 不存在")
    return record


async def list_memories(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    memory_type: str | None = None,
    agent_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[MemoryEntryRecord], int]:
    """获取记忆列表（分页 + 过滤）。"""
    base = select(MemoryEntryRecord).where(MemoryEntryRecord.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(MemoryEntryRecord.org_id == org_id)
    if user_id:
        base = base.where(MemoryEntryRecord.user_id == user_id)
    if memory_type:
        base = base.where(MemoryEntryRecord.type == memory_type)
    if agent_name:
        base = base.where(MemoryEntryRecord.agent_name == agent_name)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(MemoryEntryRecord.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def update_memory(
    db: AsyncSession, entry_id: uuid.UUID, data: MemoryUpdate
) -> MemoryEntryRecord:
    """更新记忆条目。"""
    record = await get_memory(db, entry_id)
    update_data = data.model_dump(exclude_unset=True)
    if "type" in update_data and update_data["type"] is not None:
        update_data["type"] = update_data["type"].value
    for key, value in update_data.items():
        if key == "metadata":
            record.metadata_ = value
        else:
            setattr(record, key, value)
    record.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_memory(db: AsyncSession, entry_id: uuid.UUID) -> None:
    """软删除记忆条目。"""
    record = await get_memory(db, entry_id)
    record.is_deleted = True
    record.deleted_at = datetime.now(UTC)
    await db.commit()


async def delete_user_memories(db: AsyncSession, user_id: str) -> int:
    """软删除指定用户的全部记忆条目。"""
    stmt = (
        update(MemoryEntryRecord)
        .where(MemoryEntryRecord.user_id == user_id, MemoryEntryRecord.is_deleted == False)  # noqa: E712
        .values(is_deleted=True, deleted_at=datetime.now(UTC))
    )
    result = await db.execute(stmt)
    await db.commit()
    return cast("CursorResult[Any]", result).rowcount


def _escape_like(query: str) -> str:
    """转义 LIKE/ILIKE 通配符，防止 SQL 通配符注入。"""
    return query.replace("%", "\\%").replace("_", "\\_")


async def search_memories(
    db: AsyncSession, data: MemorySearchRequest
) -> list[MemoryEntryRecord]:
    """关键词搜索记忆条目。

    MVP 版本使用 ILIKE 关键词匹配 + 置信度排序。
    后续迭代可接入 pgvector 向量检索。
    """
    escaped = _escape_like(data.query)
    stmt = (
        select(MemoryEntryRecord)
        .where(
            MemoryEntryRecord.user_id == data.user_id,
            MemoryEntryRecord.content.ilike(f"%{escaped}%"),
        )
        .order_by(
            MemoryEntryRecord.confidence.desc(),
            MemoryEntryRecord.updated_at.desc(),
        )
        .limit(data.limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def decay_memories(db: AsyncSession, data: MemoryDecayRequest) -> int:
    """对 updated_at < before 的条目降低 confidence。

    支持两种模式:
    - LINEAR: new_confidence = max(0.0, confidence - rate)
    - EXPONENTIAL: new_confidence = confidence × e^(-λ × days_since_update)
    """
    if data.mode == MemoryDecayModeEnum.EXPONENTIAL:
        return await _decay_exponential(db, data)

    # 线性衰减（原有逻辑）
    stmt = (
        update(MemoryEntryRecord)
        .where(MemoryEntryRecord.updated_at < data.before)
        .values(
            confidence=func.greatest(0.0, MemoryEntryRecord.confidence - data.rate),
            updated_at=datetime.now(UTC),
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return cast("CursorResult[Any]", result).rowcount


async def _decay_exponential(db: AsyncSession, data: MemoryDecayRequest) -> int:
    """指数衰减（艾宾浩斯遗忘曲线）。

    逐条计算 new_confidence = confidence × e^(-λ × days)，因为 days 取决于
    每条记录各自的 updated_at，无法用单条 SQL UPDATE 表达。
    """
    now = datetime.now(UTC)
    stmt = select(MemoryEntryRecord).where(
        MemoryEntryRecord.updated_at < data.before,
        MemoryEntryRecord.is_deleted == False,  # noqa: E712
    )
    rows = (await db.execute(stmt)).scalars().all()

    count = 0
    for record in rows:
        days = (now - record.updated_at).total_seconds() / 86400
        new_conf = max(0.0, record.confidence * math.exp(-data.rate * days))
        if new_conf != record.confidence:
            record.confidence = new_conf
            count += 1

    if count > 0:
        await db.commit()
    return count


# ---------------------------------------------------------------------------
# S2: count + search_by_tags
# ---------------------------------------------------------------------------


async def count_memories(db: AsyncSession, user_id: str) -> int:
    """返回指定用户的记忆条目总数。"""
    stmt = select(func.count()).where(
        MemoryEntryRecord.user_id == user_id,
        MemoryEntryRecord.is_deleted == False,  # noqa: E712
    )
    return (await db.execute(stmt)).scalar_one()


async def search_by_tags(
    db: AsyncSession, data: MemoryTagSearchRequest
) -> list[MemoryEntryRecord]:
    """按标签搜索记忆条目（OR 匹配：条目含任一标签即命中）。"""

    stmt = (
        select(MemoryEntryRecord)
        .where(
            MemoryEntryRecord.user_id == data.user_id,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
            MemoryEntryRecord.tags.overlap(data.tags),
        )
        .order_by(
            MemoryEntryRecord.confidence.desc(),
            MemoryEntryRecord.updated_at.desc(),
        )
        .limit(data.limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
