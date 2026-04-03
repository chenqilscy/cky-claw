"""SQLAlchemySessionBackend — 基于 SQLAlchemy Async 的 Session 存储后端。

实现 Framework 的 SessionBackend 接口，使用 CkyClaw Backend 已有的 SQLAlchemy 连接池。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.session.session import SessionBackend, SessionMetadata

from app.models.session_message import SessionMessage, SessionMetadataRecord

logger = logging.getLogger(__name__)


class SQLAlchemySessionBackend(SessionBackend):
    """基于 SQLAlchemy Async 的 Session 消息持久化后端。

    与 Backend 共享同一个 AsyncSession（同一个连接池），避免额外的连接管理。

    参数:
        db: SQLAlchemy AsyncSession 实例。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def load(self, session_id: str) -> list[Message] | None:
        """加载会话历史消息。"""
        stmt = (
            select(SessionMessage)
            .where(SessionMessage.session_id == session_id)
            .order_by(SessionMessage.id)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        if not rows:
            return None

        messages: list[Message] = []
        for row in rows:
            token_usage = None
            if row.token_usage:
                tu = row.token_usage
                token_usage = TokenUsage(
                    prompt_tokens=tu.get("prompt_tokens", 0),
                    completion_tokens=tu.get("completion_tokens", 0),
                    total_tokens=tu.get("total_tokens", 0),
                )
            messages.append(Message(
                role=MessageRole(row.role),
                content=row.content or "",
                agent_name=row.agent_name,
                tool_call_id=row.tool_call_id,
                tool_calls=row.tool_calls,
                token_usage=token_usage,
                timestamp=row.created_at,
                metadata=row.metadata_ or {},
            ))
        return messages

    async def save(self, session_id: str, messages: list[Message]) -> None:
        """追加保存新消息。"""
        if not messages:
            return

        for msg in messages:
            record = SessionMessage(
                session_id=session_id,
                role=msg.role.value,
                content=msg.content,
                agent_name=msg.agent_name,
                tool_call_id=msg.tool_call_id,
                tool_calls=msg.tool_calls,
                token_usage=(
                    {
                        "prompt_tokens": msg.token_usage.prompt_tokens,
                        "completion_tokens": msg.token_usage.completion_tokens,
                        "total_tokens": msg.token_usage.total_tokens,
                    }
                    if msg.token_usage
                    else None
                ),
                metadata_=msg.metadata or {},
            )
            self._db.add(record)

        await self._db.flush()

        # 更新元数据
        last_agent: str | None = None
        for m in reversed(messages):
            if m.agent_name:
                last_agent = m.agent_name
                break

        # UPSERT session_metadata
        existing = await self._db.get(SessionMetadataRecord, session_id)
        if existing is None:
            meta = SessionMetadataRecord(
                session_id=session_id,
                message_count=len(messages),
                last_agent=last_agent,
                updated_at=datetime.now(timezone.utc),
            )
            self._db.add(meta)
        else:
            existing.message_count += len(messages)
            if last_agent:
                existing.last_agent = last_agent
            existing.updated_at = datetime.now(timezone.utc)

        await self._db.flush()

    async def delete(self, session_id: str) -> None:
        """删除会话消息和元数据。"""
        from sqlalchemy import delete as sa_delete

        await self._db.execute(
            sa_delete(SessionMessage).where(SessionMessage.session_id == session_id)
        )
        await self._db.execute(
            sa_delete(SessionMetadataRecord).where(SessionMetadataRecord.session_id == session_id)
        )
        await self._db.flush()

    async def list_sessions(self, **filters: Any) -> list[SessionMetadata]:
        """列出会话元数据。"""
        stmt = select(SessionMetadataRecord).order_by(SessionMetadataRecord.updated_at.desc())
        rows = (await self._db.execute(stmt)).scalars().all()
        return [
            SessionMetadata(
                session_id=row.session_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                message_count=row.message_count,
                total_tokens=row.total_tokens,
                last_agent_name=row.last_agent,
                extra=row.extra or {},
            )
            for row in rows
        ]

    async def load_metadata(self, session_id: str) -> SessionMetadata | None:
        """加载会话元数据。"""
        row = await self._db.get(SessionMetadataRecord, session_id)
        if row is None:
            return None
        return SessionMetadata(
            session_id=row.session_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_count=row.message_count,
            total_tokens=row.total_tokens,
            last_agent_name=row.last_agent,
            extra=row.extra or {},
        )
