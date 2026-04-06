"""checkpoint_table

Revision ID: 0043
Revises: 0042
Create Date: 2026-04-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkpoints",
        sa.Column("checkpoint_id", sa.String(64), primary_key=True, comment="Checkpoint 唯一标识"),
        sa.Column("run_id", sa.String(64), nullable=False, index=True, comment="所属运行 ID"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0", comment="当前回合数"),
        sa.Column("current_agent_name", sa.String(128), nullable=False, server_default="", comment="当前 Agent 名称"),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default="[]", comment="消息历史 JSON"),
        sa.Column("token_usage", postgresql.JSONB(), nullable=False, server_default="{}", comment="Token 用量"),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}", comment="自定义上下文"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间"),
    )


def downgrade() -> None:
    op.drop_table("checkpoints")
