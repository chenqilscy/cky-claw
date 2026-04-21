"""Session（会话）数据模型。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class SessionRecord(SoftDeleteMixin, Base):
    """会话记录表 — 追踪会话元数据与 Agent 绑定关系。

    消息历史由 Framework 的 PostgresSessionBackend 管理（kasaya_sessions 表）。
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    title: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )
