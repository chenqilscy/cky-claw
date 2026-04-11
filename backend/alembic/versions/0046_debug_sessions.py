"""创建 debug_sessions 表 — Agent 调试会话。

Revision ID: 0046
Revises: 0045
Create Date: 2025-07-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 debug_sessions 表。"""
    op.create_table(
        "debug_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=False, index=True),
        sa.Column("agent_name", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="step_turn"),
        sa.Column("input_message", sa.String(4096), nullable=False, server_default=""),
        sa.Column("current_turn", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_agent_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("pause_context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("token_usage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", sa.String(8192), nullable=True),
        sa.Column("error", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """删除 debug_sessions 表。"""
    op.drop_table("debug_sessions")
