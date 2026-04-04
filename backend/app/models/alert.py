"""AlertRule / AlertEvent ORM 模型 — APM 告警规则与事件。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class AlertRule(SoftDeleteMixin, Base):
    """告警规则表。"""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    metric: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # error_rate / avg_duration_ms / total_cost / total_tokens
    operator: Mapped[str] = mapped_column(
        String(4), nullable=False
    )  # > / >= / < / <= / ==
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="60"
    )  # 检测时间窗口（分钟）
    agent_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # 监控目标 Agent，None 表示全局
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="warning"
    )  # critical / warning / info
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )  # 冷却时间（同一规则触发间隔）
    notification_config: Mapped[dict] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )  # {"webhook_url": "...", "channels": [...]}
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AlertEvent(Base):
    """告警事件表 — 规则触发记录。"""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=False, index=True
    )
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
