"""EventJournal 事件日志数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventRecord(Base):
    """事件日志记录 — 细粒度 Agent 运行事件。"""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="递增序列号（同一 run 内单调递增）",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="事件类型（run_start / llm_call_end / tool_call_start 等）",
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="所属运行 ID",
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
        comment="所属会话 ID",
    )
    agent_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True,
        comment="相关 Agent 名称",
    )
    span_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="关联的 Span ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        server_default=text("now()"),
        comment="事件时间戳",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="事件附加数据",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=text("now()"),
    )
