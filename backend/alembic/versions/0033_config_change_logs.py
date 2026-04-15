"""config_change_logs 配置变更审计日志表

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_change_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("config_key", sa.String(255), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("change_source", sa.String(20), nullable=False, server_default="api"),
        sa.Column("rollback_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("config_change_logs")
