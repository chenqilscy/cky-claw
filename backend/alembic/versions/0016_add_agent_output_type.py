"""Agent output_type 结构化输出 — agent_configs 添加 output_type JSONB 列。

Revision ID: 0016
Revises: 0015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("output_type", JSONB, nullable=True, comment="结构化输出 JSON Schema"),
    )


def downgrade() -> None:
    op.drop_column("agent_configs", "output_type")
