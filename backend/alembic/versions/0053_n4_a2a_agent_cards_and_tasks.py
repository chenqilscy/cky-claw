"""N4: A2A Agent Cards 和 Tasks 表

Revision ID: 0053
Revises: 0052
Create Date: 2026-04-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a2a_agent_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("url", sa.String(512), nullable=False, server_default=""),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("capabilities", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("authentication", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_a2a_agent_cards_agent_id", "a2a_agent_cards", ["agent_id"])
    op.create_index("ix_a2a_agent_cards_name", "a2a_agent_cards", ["name"])
    op.create_index("ix_a2a_agent_cards_org_id", "a2a_agent_cards", ["org_id"])

    op.create_table(
        "a2a_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("input_messages", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("artifacts", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("history", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_card_id"], ["a2a_agent_cards.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_a2a_tasks_agent_card_id", "a2a_tasks", ["agent_card_id"])
    op.create_index("ix_a2a_tasks_org_id", "a2a_tasks", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_a2a_tasks_org_id")
    op.drop_index("ix_a2a_tasks_agent_card_id")
    op.drop_table("a2a_tasks")
    op.drop_index("ix_a2a_agent_cards_org_id")
    op.drop_index("ix_a2a_agent_cards_name")
    op.drop_index("ix_a2a_agent_cards_agent_id")
    op.drop_table("a2a_agent_cards")
