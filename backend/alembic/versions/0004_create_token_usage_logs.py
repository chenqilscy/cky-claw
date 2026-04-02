"""create token_usage_logs table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("span_id", sa.String(64), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_token_usage_logs_trace_id", "token_usage_logs", ["trace_id"])
    op.create_index("ix_token_usage_logs_session_id", "token_usage_logs", ["session_id"])
    op.create_index("ix_token_usage_logs_user_id", "token_usage_logs", ["user_id"])
    op.create_index("ix_token_usage_logs_agent_name", "token_usage_logs", ["agent_name"])
    op.create_index(
        "ix_token_usage_logs_timestamp",
        "token_usage_logs",
        [sa.text("timestamp DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_token_usage_logs_timestamp", table_name="token_usage_logs")
    op.drop_index("ix_token_usage_logs_agent_name", table_name="token_usage_logs")
    op.drop_index("ix_token_usage_logs_user_id", table_name="token_usage_logs")
    op.drop_index("ix_token_usage_logs_session_id", table_name="token_usage_logs")
    op.drop_index("ix_token_usage_logs_trace_id", table_name="token_usage_logs")
    op.drop_table("token_usage_logs")
