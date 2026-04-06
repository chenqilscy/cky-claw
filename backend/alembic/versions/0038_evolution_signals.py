"""evolution_signals 表

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0038"
down_revision = "0037"


def upgrade() -> None:
    """创建 evolution_signals 表。"""
    op.create_table(
        "evolution_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_name", sa.String(64), nullable=False, index=True),
        sa.Column("signal_type", sa.String(32), nullable=False, index=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("call_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("success_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("avg_duration_ms", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("negative_rate", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # 复合索引：agent_name + signal_type 联合查询
    op.create_index(
        "ix_evolution_signals_agent_type",
        "evolution_signals",
        ["agent_name", "signal_type"],
    )


def downgrade() -> None:
    """删除 evolution_signals 表。"""
    op.drop_index("ix_evolution_signals_agent_type", table_name="evolution_signals")
    op.drop_table("evolution_signals")
