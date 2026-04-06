"""trace_agent_start_composite_idx

Revision ID: 0044
Revises: 0043
Create Date: 2026-04-06
"""

from __future__ import annotations

from alembic import op

revision = "0044"
down_revision = "0043"


def upgrade() -> None:
    """添加 traces 表 (agent_name, start_time) 复合索引，加速 realtime-status 聚合查询。"""
    op.create_index(
        "ix_traces_agent_start",
        "traces",
        ["agent_name", "start_time"],
    )


def downgrade() -> None:
    """移除复合索引。"""
    op.drop_index("ix_traces_agent_start", table_name="traces")
