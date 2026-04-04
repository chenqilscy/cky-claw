"""AuditLog（审计日志）数据模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """审计日志表 — 记录用户对资源的所有写操作。"""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status_code: Mapped[int | None] = mapped_column(
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
