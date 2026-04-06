"""provider_add_key_expiry_rotation

Revision ID: 0042
Revises: 0041
Create Date: 2026-04-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_configs",
        sa.Column("key_expires_at", sa.DateTime(timezone=True), nullable=True,
                  comment="API Key 过期时间，NULL 表示永不过期"),
    )
    op.add_column(
        "provider_configs",
        sa.Column("key_last_rotated_at", sa.DateTime(timezone=True), nullable=True,
                  comment="API Key 最近一次轮换时间"),
    )


def downgrade() -> None:
    op.drop_column("provider_configs", "key_last_rotated_at")
    op.drop_column("provider_configs", "key_expires_at")
