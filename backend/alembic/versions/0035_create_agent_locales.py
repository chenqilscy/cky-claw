"""create agent_locales

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 agent_locales 表。"""
    op.create_table(
        "agent_locales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("locale", sa.String(16), nullable=False, comment="BCP 47 语言标识"),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("agent_id", "locale", name="uq_agent_locales_agent_locale"),
    )


def downgrade() -> None:
    """删除 agent_locales 表。"""
    op.drop_table("agent_locales")
