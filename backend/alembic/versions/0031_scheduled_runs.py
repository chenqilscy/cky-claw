"""scheduled_runs 执行历史表

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("scheduled_tasks.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("trace_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("triggered_by", sa.String(20), nullable=False, server_default="scheduler"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("scheduled_runs")
