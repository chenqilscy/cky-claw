"""PostgreSQL Checkpoint 存储后端 — 实现 Framework CheckpointBackend ABC。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.models.checkpoint import CheckpointRecord
from kasaya.checkpoint import Checkpoint, CheckpointBackend
from kasaya.model.message import Message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PostgresCheckpointBackend(CheckpointBackend):  # type: ignore[misc]
    """基于 PostgreSQL + SQLAlchemy 的 Checkpoint 持久化后端。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, checkpoint: Checkpoint) -> None:
        """保存 checkpoint 到 PostgreSQL。"""
        record = CheckpointRecord(
            checkpoint_id=checkpoint.checkpoint_id,
            run_id=checkpoint.run_id,
            turn_count=checkpoint.turn_count,
            current_agent_name=checkpoint.current_agent_name,
            messages=[m.to_dict() if isinstance(m, Message) else m for m in checkpoint.messages],
            token_usage=checkpoint.token_usage,
            context=checkpoint.context,
            created_at=checkpoint.created_at,
        )
        self._db.add(record)
        await self._db.flush()

    async def load_latest(self, run_id: str) -> Checkpoint | None:
        """加载指定 run_id 的最新 checkpoint。"""
        stmt = (
            select(CheckpointRecord)
            .where(CheckpointRecord.run_id == run_id)
            .order_by(CheckpointRecord.turn_count.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_checkpoint(row)

    async def list_checkpoints(self, run_id: str) -> list[Checkpoint]:
        """列出指定 run_id 的所有 checkpoint（按 turn_count 升序）。"""
        stmt = (
            select(CheckpointRecord)
            .where(CheckpointRecord.run_id == run_id)
            .order_by(CheckpointRecord.turn_count.asc())
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return [self._to_checkpoint(r) for r in rows]

    async def delete(self, run_id: str) -> None:
        """删除指定 run_id 的全部 checkpoint。"""
        stmt = delete(CheckpointRecord).where(CheckpointRecord.run_id == run_id)
        await self._db.execute(stmt)
        await self._db.flush()

    @staticmethod
    def _to_checkpoint(record: CheckpointRecord) -> Checkpoint:
        """将 ORM 记录转为 Checkpoint dataclass。"""
        messages = [Message.from_dict(m) for m in (record.messages or [])]
        return Checkpoint(
            checkpoint_id=record.checkpoint_id,
            run_id=record.run_id,
            turn_count=record.turn_count,
            current_agent_name=record.current_agent_name,
            messages=messages,
            token_usage=record.token_usage or {},
            context=record.context or {},
            created_at=record.created_at,
        )
