"""Agent 运行评估数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RunEvaluation(Base):
    """Agent 运行评估表 — 7 维度质量度量。"""

    __tablename__ = "run_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # 7 维度评分（0.0-1.0）
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    relevance: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    coherence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    helpfulness: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    safety: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    efficiency: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    tool_usage: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    # 综合分
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    # 评估方式
    eval_method: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'manual'")
    )
    evaluator: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class RunFeedback(Base):
    """用户反馈表 — 运行结果的 👍/👎 + 文字反馈。"""

    __tablename__ = "run_feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
