"""多租户隔离 — organizations 表 + 核心表 org_id 列

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

# 需要添加 org_id 列的表（agent_configs 已有 org_id，需单独处理外键）
_TABLES_WITH_ORG_ID = [
    "users",
    "sessions",
    "team_configs",
    "workflow_definitions",
    "memory_entries",
    "skills",
    "im_channels",
    "guardrail_rules",
    "tool_group_configs",
]


def upgrade() -> None:
    # 1. 创建 organizations 表
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("quota", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. 为核心表添加 org_id 列 + 索引 + 外键
    for table in _TABLES_WITH_ORG_ID:
        op.add_column(table, sa.Column("org_id", UUID(as_uuid=True), nullable=True))
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])
        op.create_foreign_key(
            f"fk_{table}_org_id",
            table,
            "organizations",
            ["org_id"],
            ["id"],
        )

    # 3. agent_configs 已有 org_id 列，仅添加外键约束
    op.create_foreign_key(
        "fk_agent_configs_org_id",
        "agent_configs",
        "organizations",
        ["org_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_configs_org_id", "agent_configs", type_="foreignkey")
    for table in reversed(_TABLES_WITH_ORG_ID):
        op.drop_constraint(f"fk_{table}_org_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_column(table, "org_id")
    op.drop_table("organizations")
