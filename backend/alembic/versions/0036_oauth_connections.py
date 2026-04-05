"""OAuth 认证 — user_oauth_connections 表 + users.avatar_url 字段

Revision ID: 0036
Revises: 0035
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 user_oauth_connections 表 + users.avatar_url 列。"""
    op.create_table(
        "user_oauth_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False, index=True),
        sa.Column("provider_user_id", sa.String(256), nullable=False),
        sa.Column("provider_username", sa.String(256), nullable=False, server_default=""),
        sa.Column("provider_email", sa.String(256), nullable=True),
        sa.Column("provider_avatar_url", sa.String(1024), nullable=True),
        sa.Column("access_token_encrypted", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    op.add_column("users", sa.Column("avatar_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    """移除 user_oauth_connections 表 + users.avatar_url 列。"""
    op.drop_column("users", "avatar_url")
    op.drop_table("user_oauth_connections")
