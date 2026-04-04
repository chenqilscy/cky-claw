"""条件启用 — guardrail_rules + tool_group_configs 添加 conditions JSONB

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guardrail_rules",
        sa.Column("conditions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "tool_group_configs",
        sa.Column("conditions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("tool_group_configs", "conditions")
    op.drop_column("guardrail_rules", "conditions")
