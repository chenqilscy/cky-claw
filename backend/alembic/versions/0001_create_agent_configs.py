"""create agent_configs table

Revision ID: 0001
Revises:
Create Date: 2026-04-03

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("model_settings", pg.JSONB(), nullable=True),
        sa.Column("tool_groups", pg.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("handoffs", pg.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("guardrails", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("approval_mode", sa.String(16), nullable=False, server_default="suggest"),
        sa.Column("mcp_servers", pg.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("skills", pg.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("metadata", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("org_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_configs_name", "agent_configs", ["name"], unique=True)
    op.create_index("ix_agent_configs_org_id", "agent_configs", ["org_id"])
    op.create_index("ix_agent_configs_is_active", "agent_configs", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_is_active", table_name="agent_configs")
    op.drop_index("ix_agent_configs_org_id", table_name="agent_configs")
    op.drop_index("ix_agent_configs_name", table_name="agent_configs")
    op.drop_table("agent_configs")
