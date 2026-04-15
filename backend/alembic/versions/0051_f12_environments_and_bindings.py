"""F12 创建 environments 与 agent_environment_bindings 表。

Revision ID: 0051
Revises: 0050
Create Date: 2026-04-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers
revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建环境与发布绑定表，并插入内置环境。"""
    op.create_table(
        "environments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("color", sa.String(16), nullable=False, server_default=sa.text("'#1890ff'")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_protected", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("settings_override", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_environments_name", "environments", ["name"], unique=True)
    op.create_index("ix_environments_org_id", "environments", ["org_id"], unique=False)

    op.create_table(
        "agent_environment_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "agent_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("environments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_config_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rollback_from_id", UUID(as_uuid=True), sa.ForeignKey("agent_environment_bindings.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.UniqueConstraint("agent_config_id", "environment_id", name="uq_agent_environment_binding"),
    )
    op.create_index("ix_agent_environment_bindings_agent_config_id", "agent_environment_bindings", ["agent_config_id"], unique=False)
    op.create_index("ix_agent_environment_bindings_environment_id", "agent_environment_bindings", ["environment_id"], unique=False)
    op.create_index("ix_agent_environment_bindings_version_id", "agent_environment_bindings", ["version_id"], unique=False)
    op.create_index("ix_agent_environment_bindings_org_id", "agent_environment_bindings", ["org_id"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO environments (name, display_name, color, sort_order, is_protected)
            VALUES
              ('dev', '开发', '#52c41a', 0, false),
              ('staging', '预发', '#faad14', 1, false),
              ('prod', '生产', '#f5222d', 2, true)
            ON CONFLICT (name) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """回滚环境相关表。"""
    op.drop_index("ix_agent_environment_bindings_org_id", table_name="agent_environment_bindings")
    op.drop_index("ix_agent_environment_bindings_version_id", table_name="agent_environment_bindings")
    op.drop_index("ix_agent_environment_bindings_environment_id", table_name="agent_environment_bindings")
    op.drop_index("ix_agent_environment_bindings_agent_config_id", table_name="agent_environment_bindings")
    op.drop_table("agent_environment_bindings")

    op.drop_index("ix_environments_org_id", table_name="environments")
    op.drop_index("ix_environments_name", table_name="environments")
    op.drop_table("environments")
