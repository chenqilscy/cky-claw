"""Agent 评估与反馈表

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("accuracy", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("relevance", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("coherence", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("helpfulness", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("safety", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("efficiency", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("tool_usage", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("overall_score", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("eval_method", sa.String(32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evaluator", sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "run_feedbacks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("run_feedbacks")
    op.drop_table("run_evaluations")
