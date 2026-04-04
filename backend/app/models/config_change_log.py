"""ConfigChangeLog ORM 模型 — 配置变更审计日志。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfigChangeLog(Base):
    """配置变更日志表 — 记录每次配置变更，支持审计与回滚。"""

    __tablename__ = "config_change_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_key: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="配置项键名，如 agent.triage.instructions"
    )
    entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="实体类型：agent/guardrail/provider/tool-group 等"
    )
    entity_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="实体 ID"
    )
    old_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="变更前的完整值"
    )
    new_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="变更后的完整值"
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="操作人"
    )
    change_source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="api", comment="变更来源：web_ui/api/system/rollback"
    )
    rollback_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="回滚引用的原始变更 ID"
    )
    description: Mapped[str] = mapped_column(
        Text, server_default="", nullable=False, comment="变更描述"
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
