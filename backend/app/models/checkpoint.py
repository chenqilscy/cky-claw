"""Checkpoint 数据模型 — Agent 运行循环中间状态持久化。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CheckpointRecord(Base):
    """Checkpoint 持久化记录。"""

    __tablename__ = "checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="Checkpoint 唯一标识"
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="所属运行 ID"
    )
    turn_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="当前回合数"
    )
    current_agent_name: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("''"), comment="当前 Agent 名称"
    )
    messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"),
        comment="完整消息历史（JSON 序列化）",
    )
    token_usage: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="累计 Token 用量",
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="用户自定义上下文",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Checkpoint 创建时间",
    )
