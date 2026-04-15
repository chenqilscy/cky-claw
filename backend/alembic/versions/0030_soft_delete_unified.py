"""软删除统一 — 为 15 个核心模型添加 is_deleted + deleted_at 字段。

Revision ID: 0030
Revises: 0029
Create Date: 2025-07-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

# 需要添加软删除字段的表
_TABLES = [
    "agent_configs",
    "agent_templates",
    "guardrail_rules",
    "im_channels",
    "mcp_server_configs",
    "memory_entries",
    "organizations",
    "provider_configs",
    "provider_models",
    "scheduled_tasks",
    "sessions",
    "skills",
    "team_configs",
    "tool_group_configs",
    "workflow_definitions",
]


def upgrade() -> None:
    """为所有核心实体表添加 is_deleted 和 deleted_at 列。"""
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_is_deleted", table, ["is_deleted"])


def downgrade() -> None:
    """移除 is_deleted 和 deleted_at 列。"""
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_is_deleted", table_name=table)
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "is_deleted")
