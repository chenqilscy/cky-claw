"""创建工作流定义表 workflow_definitions。

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("steps", JSONB, nullable=False, server_default="[]"),
        sa.Column("edges", JSONB, nullable=False, server_default="[]"),
        sa.Column("input_schema", JSONB, nullable=True),
        sa.Column("output_keys", JSONB, nullable=True),
        sa.Column("timeout", sa.Float, nullable=True),
        sa.Column("guardrail_names", JSONB, nullable=True),
        sa.Column("metadata_", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_workflow_name", "workflow_definitions", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_workflow_name", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
