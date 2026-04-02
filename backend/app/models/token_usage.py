"""Token 审计日志数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TokenUsageLog(Base):
    """Token 消耗记录 — 按 LLM Span 粒度记录每次调用的 Token 消耗。"""

    __tablename__ = "token_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    span_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
