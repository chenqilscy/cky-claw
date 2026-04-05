"""OAuth 绑定数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserOAuthConnection(Base):
    """用户 OAuth 绑定表 — 记录用户与第三方 OAuth Provider 的关联。"""

    __tablename__ = "user_oauth_connections"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(256), nullable=False
    )
    provider_username: Mapped[str] = mapped_column(
        String(256), nullable=False, server_default=text("''")
    )
    provider_email: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    provider_avatar_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
