"""S4 创建 events 事件日志表。

Revision ID: 0048
Revises: 0047
Create Date: 2026-04-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers
revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 events 表，支持事件溯源与回放。"""
    op.create_table(
        "events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sequence", sa.Integer, nullable=False, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("agent_name", sa.String(128), nullable=True, index=True),
        sa.Column("span_id", sa.String(64), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    """删除 events 表。"""
    op.drop_table("events")
