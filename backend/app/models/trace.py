"""Trace 追踪数据模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TraceRecord(Base):
    """Trace 记录 — 完整执行链路。"""

    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    workflow_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="default", index=True
    )
    group_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    agent_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed"
    )
    span_count: Mapped[int] = mapped_column(
        nullable=False, default=0
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(
        nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class SpanRecord(Base):
    """Span 记录 — 执行步骤追踪。"""

    __tablename__ = "spans"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    trace_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    parent_span_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(256), nullable=False, default=""
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed"
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(
        nullable=True
    )
    input_data: Mapped[dict[str, Any] | None] = mapped_column(
        "input", JSONB, nullable=True
    )
    output_data: Mapped[dict[str, Any] | None] = mapped_column(
        "output", JSONB, nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    model: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
