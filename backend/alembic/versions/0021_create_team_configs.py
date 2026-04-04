"""create team_configs table

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("protocol", sa.String(32), nullable=False, server_default="SEQUENTIAL"),
        sa.Column("member_agent_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("coordinator_agent_id", sa.String(64), nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("team_configs")
