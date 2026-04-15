"""IM 渠道表

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "im_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("channel_type", sa.String(32), nullable=False),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("webhook_secret", sa.Text, nullable=True),
        sa.Column("app_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("im_channels")
