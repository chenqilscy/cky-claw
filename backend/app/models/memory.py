"""MemoryEntry（记忆条目）数据模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class MemoryEntryRecord(SoftDeleteMixin, Base):
    """记忆条目表 — 跨会话的长期记忆存储。"""

    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1.0")
    )
    agent_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    source_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float), nullable=True, default=None
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )
    access_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
