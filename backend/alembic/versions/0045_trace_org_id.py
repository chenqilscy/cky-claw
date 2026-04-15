"""TraceRecord 添加 org_id 字段，支持多租户过滤。

Revision ID: 0045
Revises: 0044
Create Date: 2025-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 org_id 列和索引。"""
    op.add_column(
        "traces",
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
    )
    op.create_index("ix_traces_org_id", "traces", ["org_id"])


def downgrade() -> None:
    """移除 org_id 列和索引。"""
    op.drop_index("ix_traces_org_id", table_name="traces")
    op.drop_column("traces", "org_id")
