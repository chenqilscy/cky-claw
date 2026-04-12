"""N7: Benchmark suites and runs.

Revision ID: 0056
Revises: 0055
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, index=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("agent_name", sa.String(120), server_default=""),
        sa.Column("model", sa.String(120), server_default=""),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "suite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benchmark_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("total_cases", sa.Integer, server_default="0"),
        sa.Column("passed_cases", sa.Integer, server_default="0"),
        sa.Column("failed_cases", sa.Integer, server_default="0"),
        sa.Column("error_cases", sa.Integer, server_default="0"),
        sa.Column("overall_score", sa.Float, server_default="0.0"),
        sa.Column("pass_rate", sa.Float, server_default="0.0"),
        sa.Column("total_latency_ms", sa.Float, server_default="0.0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("dimension_summaries", postgresql.JSONB, nullable=True),
        sa.Column("report", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("benchmark_runs")
    op.drop_table("benchmark_suites")
