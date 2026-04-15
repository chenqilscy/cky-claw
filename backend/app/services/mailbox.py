"""Mailbox 业务逻辑层。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, or_, select, update

from app.core.exceptions import NotFoundError
from app.models.mailbox import MailboxRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.mailbox import MailboxSendRequest


async def send_message(db: AsyncSession, data: MailboxSendRequest) -> MailboxRecord:
    """发送消息。"""
    record = MailboxRecord(
        id=uuid.uuid4(),
        run_id=data.run_id,
        from_agent=data.from_agent,
        to_agent=data.to_agent,
        content=data.content,
        message_type=data.message_type,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.flush()
    return record


async def receive_messages(
    db: AsyncSession,
    agent_name: str,
    *,
    run_id: str | None = None,
    unread_only: bool = True,
) -> list[MailboxRecord]:
    """接收指定 Agent 的消息。"""
    conditions = [MailboxRecord.to_agent == agent_name]
    if run_id is not None:
        conditions.append(MailboxRecord.run_id == run_id)
    if unread_only:
        conditions.append(MailboxRecord.is_read == False)  # noqa: E712

    stmt = (
        select(MailboxRecord)
        .where(*conditions)
        .order_by(MailboxRecord.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_read(db: AsyncSession, message_id: uuid.UUID) -> None:
    """标记消息为已读。"""
    stmt = (
        update(MailboxRecord)
        .where(MailboxRecord.id == message_id)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotFoundError(f"消息 '{message_id}' 不存在")
    await db.flush()


async def get_conversation(
    db: AsyncSession,
    run_id: str,
    agent_a: str,
    agent_b: str,
) -> list[MailboxRecord]:
    """获取两个 Agent 之间的对话历史。"""
    stmt = (
        select(MailboxRecord)
        .where(
            MailboxRecord.run_id == run_id,
            or_(
                and_(MailboxRecord.from_agent == agent_a, MailboxRecord.to_agent == agent_b),
                and_(MailboxRecord.from_agent == agent_b, MailboxRecord.to_agent == agent_a),
            ),
        )
        .order_by(MailboxRecord.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_run_messages(db: AsyncSession, run_id: str) -> int:
    """删除指定 Run 的所有消息。返回删除数量。"""
    stmt = delete(MailboxRecord).where(MailboxRecord.run_id == run_id)
    result = await db.execute(stmt)
    await db.flush()
    return int(result.rowcount)  # type: ignore[attr-defined]
