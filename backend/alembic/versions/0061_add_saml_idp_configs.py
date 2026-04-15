"""add saml_idp_configs table

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saml_idp_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("entity_id", sa.String(512), nullable=False, unique=True),
        sa.Column("sso_url", sa.String(1024), nullable=False),
        sa.Column("slo_url", sa.String(1024), nullable=False, server_default=sa.text("''")),
        sa.Column("x509_cert", sa.Text(), nullable=False),
        sa.Column("metadata_xml", sa.Text(), nullable=True),
        sa.Column(
            "attribute_mapping",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    )


def downgrade() -> None:
    op.drop_table("saml_idp_configs")
