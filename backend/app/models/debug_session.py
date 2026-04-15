"""DebugSession ORM 模型 — 调试会话元数据持久化。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DebugSession(Base):
    """调试会话记录。

    存储调试会话的元数据和状态，实际的暂停/恢复逻辑在内存中的
    DebugController 管理。该表用于：
    - 查询历史调试会话
    - 记录调试会话生命周期
    - 前端列表展示
    """

    __tablename__ = "debug_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False, index=True,
    )
    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="idle",
    )
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="step_turn",
    )
    input_message: Mapped[str] = mapped_column(
        String(4096), nullable=False, default="",
    )
    current_turn: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    current_agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    pause_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )
    token_usage: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )
    result: Mapped[str | None] = mapped_column(
        String(8192), nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
