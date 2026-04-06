"""进化建议 ORM 模型。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvolutionProposalRecord(Base):
    """进化建议记录表。"""

    __tablename__ = "evolution_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    proposal_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    """instructions / tools / guardrails / model / memory"""

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'"), index=True
    )
    """pending / approved / rejected / applied / rolled_back"""

    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    current_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    proposed_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )

    eval_before: Mapped[float | None] = mapped_column(Float, nullable=True)

    eval_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
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
