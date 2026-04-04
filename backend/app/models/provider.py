"""Model Provider 配置数据模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class ProviderConfig(SoftDeleteMixin, Base):
    """模型厂商配置表 — 对应 Data Model v1.3 的 ProviderConfig。"""

    __tablename__ = "provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    base_url: Mapped[str] = mapped_column(
        String(512), nullable=False
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    auth_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'api_key'")
    )
    auth_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    rate_limit_rpm: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    rate_limit_tpm: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    health_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unknown'")
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
