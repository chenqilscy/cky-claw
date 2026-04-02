"""create guardrail_rules

Revision ID: 0007
Revises: 0006
Create Date: 2025-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guardrail_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("type", sa.String(16), nullable=False, server_default="input"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="regex"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_guardrail_rules_name", "guardrail_rules", ["name"])
    op.create_index("ix_guardrail_rules_type", "guardrail_rules", ["type"])
    op.create_index("ix_guardrail_rules_is_enabled", "guardrail_rules", ["is_enabled"])


def downgrade() -> None:
    op.drop_index("ix_guardrail_rules_is_enabled", table_name="guardrail_rules")
    op.drop_index("ix_guardrail_rules_type", table_name="guardrail_rules")
    op.drop_index("ix_guardrail_rules_name", table_name="guardrail_rules")
    op.drop_table("guardrail_rules")
