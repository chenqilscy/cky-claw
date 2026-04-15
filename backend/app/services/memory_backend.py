"""SQLAlchemyMemoryBackend — 基于 SQLAlchemy Async 的记忆存储后端。

实现 Framework 的 MemoryBackend 接口，使用 CkyClaw Backend 已有的 SQLAlchemy 连接池。
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from app.models.memory import MemoryEntryRecord
from ckyclaw_framework.memory.memory import (
    DecayMode,
    MemoryBackend,
    MemoryEntry,
    MemoryType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _record_to_entry(record: MemoryEntryRecord) -> MemoryEntry:
    """ORM 记录 → Framework MemoryEntry。"""
    return MemoryEntry(
        id=str(record.id),
        type=MemoryType(record.type),
        content=record.content,
        confidence=record.confidence,
        user_id=record.user_id,
        agent_name=record.agent_name,
        source_session_id=record.source_session_id,
        metadata=record.metadata_ or {},
        embedding=record.embedding,
        tags=record.tags or [],
        access_count=record.access_count or 0,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SQLAlchemyMemoryBackend(MemoryBackend):  # type: ignore[misc]
    """基于 SQLAlchemy Async 的记忆存储后端。

    与 Backend 共享同一个 AsyncSession（同一个连接池），避免额外的连接管理。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def store(self, user_id: str, entry: MemoryEntry) -> None:
        """存储或更新一条记忆条目（upsert）。"""
        if not user_id:
            raise ValueError("user_id 不能为空")

        import uuid as _uuid

        # 尝试查找已有记录
        try:
            entry_uuid = _uuid.UUID(entry.id)
        except (ValueError, AttributeError):
            entry_uuid = _uuid.uuid4()

        stmt = select(MemoryEntryRecord).where(
            MemoryEntryRecord.id == entry_uuid,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
        )
        existing = (await self._db.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            if existing.user_id != user_id:
                raise PermissionError("不能修改其他用户的记忆条目")
            existing.content = entry.content
            existing.confidence = entry.confidence
            existing.type = entry.type.value
            existing.agent_name = entry.agent_name
            existing.source_session_id = entry.source_session_id
            existing.metadata_ = entry.metadata
            existing.embedding = entry.embedding
            existing.tags = entry.tags
            existing.access_count = entry.access_count
            existing.updated_at = datetime.now(UTC)
        else:
            record = MemoryEntryRecord(
                id=entry_uuid,
                user_id=user_id,
                type=entry.type.value,
                content=entry.content,
                confidence=entry.confidence,
                agent_name=entry.agent_name,
                source_session_id=entry.source_session_id,
                metadata_=entry.metadata,
                embedding=entry.embedding,
                tags=entry.tags,
                access_count=entry.access_count,
            )
            self._db.add(record)

        await self._db.flush()

    async def search(
        self, user_id: str, query: str, *, limit: int = 10
    ) -> list[MemoryEntry]:
        """关键词搜索用户记忆条目。"""
        if not query:
            return []
        escaped = query.replace("%", "\\%").replace("_", "\\_")
        stmt = (
            select(MemoryEntryRecord)
            .where(
                MemoryEntryRecord.user_id == user_id,
                MemoryEntryRecord.is_deleted == False,  # noqa: E712
                MemoryEntryRecord.content.ilike(f"%{escaped}%"),
            )
            .order_by(
                MemoryEntryRecord.confidence.desc(),
                MemoryEntryRecord.updated_at.desc(),
            )
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return [_record_to_entry(r) for r in rows]

    async def list_entries(
        self,
        user_id: str,
        *,
        memory_type: MemoryType | None = None,
        agent_name: str | None = None,
    ) -> list[MemoryEntry]:
        """列出用户的记忆条目。"""
        stmt = select(MemoryEntryRecord).where(
            MemoryEntryRecord.user_id == user_id,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
        )
        if memory_type is not None:
            stmt = stmt.where(MemoryEntryRecord.type == memory_type.value)
        if agent_name is not None:
            stmt = stmt.where(MemoryEntryRecord.agent_name == agent_name)
        stmt = stmt.order_by(MemoryEntryRecord.updated_at.desc())
        rows = (await self._db.execute(stmt)).scalars().all()
        return [_record_to_entry(r) for r in rows]

    async def get(self, entry_id: str) -> MemoryEntry | None:
        """获取单条记忆条目。"""
        import uuid as _uuid

        try:
            entry_uuid = _uuid.UUID(entry_id)
        except ValueError:
            return None
        stmt = select(MemoryEntryRecord).where(
            MemoryEntryRecord.id == entry_uuid,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
        )
        record = (await self._db.execute(stmt)).scalar_one_or_none()
        return _record_to_entry(record) if record else None

    async def delete(self, entry_id: str) -> None:
        """软删除一条记忆条目。"""
        import uuid as _uuid

        try:
            entry_uuid = _uuid.UUID(entry_id)
        except ValueError:
            return
        stmt = select(MemoryEntryRecord).where(MemoryEntryRecord.id == entry_uuid)
        record = (await self._db.execute(stmt)).scalar_one_or_none()
        if record:
            record.is_deleted = True
            record.deleted_at = datetime.now(UTC)
            await self._db.flush()

    async def delete_by_user(self, user_id: str) -> int:
        """软删除指定用户的全部记忆。"""
        stmt = (
            update(MemoryEntryRecord)
            .where(
                MemoryEntryRecord.user_id == user_id,
                MemoryEntryRecord.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True, deleted_at=datetime.now(UTC))
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def decay(
        self,
        before: datetime,
        rate: float,
        *,
        mode: DecayMode = DecayMode.LINEAR,
    ) -> int:
        """对 updated_at < before 的条目降低 confidence。"""
        if mode == DecayMode.LINEAR:
            stmt = (
                update(MemoryEntryRecord)
                .where(MemoryEntryRecord.updated_at < before)
                .values(
                    confidence=func.greatest(0.0, MemoryEntryRecord.confidence - rate),
                )
            )
            result = await self._db.execute(stmt)
            await self._db.flush()
            return result.rowcount or 0  # type: ignore[attr-defined]

        # 指数衰减需逐条计算
        now = datetime.now(UTC)
        select_stmt = select(MemoryEntryRecord).where(
            MemoryEntryRecord.updated_at < before,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
        )
        rows = (await self._db.execute(select_stmt)).scalars().all()
        count = 0
        for record in rows:
            days = (now - record.updated_at).total_seconds() / 86400
            new_conf = max(0.0, record.confidence * math.exp(-rate * days))
            if new_conf != record.confidence:
                record.confidence = new_conf
                count += 1
        if count > 0:
            await self._db.flush()
        return count

    async def count(self, user_id: str) -> int:
        """返回用户记忆条目总数。"""
        stmt = select(func.count()).where(
            MemoryEntryRecord.user_id == user_id,
            MemoryEntryRecord.is_deleted == False,  # noqa: E712
        )
        return (await self._db.execute(stmt)).scalar_one()

    async def search_by_tags(
        self,
        user_id: str,
        tags: list[str],
        *,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """按标签搜索用户记忆条目（OR 匹配）。"""
        if not tags:
            return []
        stmt = (
            select(MemoryEntryRecord)
            .where(
                MemoryEntryRecord.user_id == user_id,
                MemoryEntryRecord.is_deleted == False,  # noqa: E712
                MemoryEntryRecord.tags.overlap(tags),
            )
            .order_by(
                MemoryEntryRecord.confidence.desc(),
                MemoryEntryRecord.updated_at.desc(),
            )
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return [_record_to_entry(r) for r in rows]
