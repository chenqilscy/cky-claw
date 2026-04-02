"""create provider_configs table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-03

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.String(16), nullable=False, server_default="api_key"),
        sa.Column("auth_config", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=True),
        sa.Column("rate_limit_tpm", sa.Integer(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("org_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_provider_configs_name", "provider_configs", ["name"])
    op.create_index("ix_provider_configs_org_id", "provider_configs", ["org_id"])
    op.create_index("ix_provider_configs_provider_type", "provider_configs", ["provider_type"])
    op.create_index("ix_provider_configs_is_enabled", "provider_configs", ["is_enabled"])


def downgrade() -> None:
    op.drop_index("ix_provider_configs_is_enabled", table_name="provider_configs")
    op.drop_index("ix_provider_configs_provider_type", table_name="provider_configs")
    op.drop_index("ix_provider_configs_org_id", table_name="provider_configs")
    op.drop_index("ix_provider_configs_name", table_name="provider_configs")
    op.drop_table("provider_configs")
