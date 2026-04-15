"""Add response_style column to agent_configs.

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 response_style 列。"""
    op.add_column(
        "agent_configs",
        sa.Column("response_style", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    """移除 response_style 列。"""
    op.drop_column("agent_configs", "response_style")
