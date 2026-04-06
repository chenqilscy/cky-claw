"""evolution_proposals 表

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 evolution_proposals 表。"""
    op.create_table(
        "evolution_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_name", sa.String(64), nullable=False, index=True),
        sa.Column("proposal_type", sa.String(32), nullable=False, index=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
            index=True,
        ),
        sa.Column("trigger_reason", sa.Text, nullable=False, server_default=""),
        sa.Column("current_value", JSONB, nullable=True),
        sa.Column("proposed_value", JSONB, nullable=True),
        sa.Column(
            "confidence_score",
            sa.Float,
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column("eval_before", sa.Float, nullable=True),
        sa.Column("eval_after", sa.Float, nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    """删除 evolution_proposals 表。"""
    op.drop_table("evolution_proposals")
