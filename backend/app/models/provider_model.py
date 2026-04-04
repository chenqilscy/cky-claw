"""Provider Model — 模型厂商可用模型列表。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class ProviderModel(SoftDeleteMixin, Base):
    """厂商可用模型 — 记录 Provider 下可用的 LLM 模型及价格信息。"""

    __tablename__ = "provider_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_configs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("''"),
    )
    context_window: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("4096"),
    )
    max_output_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    prompt_price_per_1k: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0.0"),
    )
    completion_price_per_1k: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0.0"),
    )
    is_enabled: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true"),
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
