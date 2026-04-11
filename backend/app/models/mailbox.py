"""Mailbox 数据模型 — Agent 间通信消息持久化。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MailboxRecord(Base):
    """Mailbox 消息持久化记录。"""

    __tablename__ = "mailbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="消息唯一标识"
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="所属运行 ID"
    )
    from_agent: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="发送方 Agent 名称"
    )
    to_agent: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="接收方 Agent 名称"
    )
    content: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("''"), comment="消息内容"
    )
    message_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'handoff'"), comment="消息类型"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否已读"
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="扩展元数据",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="创建时间",
    )
