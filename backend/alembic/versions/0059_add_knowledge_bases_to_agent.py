"""Add knowledge_bases column to agent_configs.

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 knowledge_bases 列。"""
    op.add_column(
        "agent_configs",
        sa.Column(
            "knowledge_bases",
            ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )


def downgrade() -> None:
    """移除 knowledge_bases 列。"""
    op.drop_column("agent_configs", "knowledge_bases")
