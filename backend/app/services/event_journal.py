"""SQLAlchemyEventJournal — 桥接 Framework EventJournal 到 PostgreSQL。"""

from __future__ import annotations

import itertools
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ckyclaw_framework.events.journal import EventEntry, EventJournal
from ckyclaw_framework.events.types import EventType

logger = logging.getLogger(__name__)


class SQLAlchemyEventJournal(EventJournal):  # type: ignore[misc]
    """基于 SQLAlchemy 的事件日志实现。

    将 EventEntry 持久化到 PostgreSQL events 表。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._seq_counter = itertools.count(1)

    async def _append(self, entry: EventEntry) -> None:
        """将事件写入数据库。"""
        from app.models.event import EventRecord

        entry.sequence = next(self._seq_counter)

        record = EventRecord(
            id=entry.event_id if entry.event_id else None,
            sequence=entry.sequence,
            event_type=entry.event_type.value,
            run_id=entry.run_id,
            session_id=entry.session_id,
            agent_name=entry.agent_name,
            span_id=entry.span_id,
            timestamp=entry.timestamp,
            payload=entry.payload,
        )
        self._db.add(record)
        await self._db.flush()

    async def _query(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        event_types: list[EventType] | None = None,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[EventEntry]:
        """从数据库查询事件。"""
        from app.models.event import EventRecord

        stmt = select(EventRecord).order_by(EventRecord.sequence.asc())

        if run_id is not None:
            stmt = stmt.where(EventRecord.run_id == run_id)
        if session_id is not None:
            stmt = stmt.where(EventRecord.session_id == session_id)
        if event_types is not None:
            type_values = [et.value for et in event_types]
            stmt = stmt.where(EventRecord.event_type.in_(type_values))
        if after_sequence is not None:
            stmt = stmt.where(EventRecord.sequence > after_sequence)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._db.execute(stmt)
        records = result.scalars().all()

        return [
            EventEntry(
                event_id=str(r.id),
                sequence=r.sequence,
                event_type=EventType(r.event_type),
                run_id=r.run_id,
                session_id=str(r.session_id) if r.session_id else None,
                agent_name=r.agent_name,
                span_id=r.span_id,
                timestamp=r.timestamp,
                payload=r.payload or {},
            )
            for r in records
        ]
