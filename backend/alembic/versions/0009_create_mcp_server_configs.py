"""创建 mcp_server_configs 表。

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("transport_type", sa.String(16), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("env", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("auth_config", pg.JSONB(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("org_id", pg.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_mcp_server_configs_transport_type", "mcp_server_configs", ["transport_type"])
    op.create_index("ix_mcp_server_configs_is_enabled", "mcp_server_configs", ["is_enabled"])


def downgrade() -> None:
    op.drop_index("ix_mcp_server_configs_is_enabled", table_name="mcp_server_configs")
    op.drop_index("ix_mcp_server_configs_transport_type", table_name="mcp_server_configs")
    op.drop_table("mcp_server_configs")
