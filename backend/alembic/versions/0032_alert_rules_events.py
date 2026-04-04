"""alert_rules + alert_events 告警表

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(4), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("window_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("is_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("cooldown_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("notification_config", JSONB, server_default="{}", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "alert_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("alert_rules.id"), nullable=False, index=True),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
