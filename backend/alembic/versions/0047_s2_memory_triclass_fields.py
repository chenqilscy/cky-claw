"""S2 memory_entries 新增 embedding / tags / access_count 列。

Revision ID: 0047
Revises: 0046
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers
revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """memory_entries 表新增 S2 字段。"""
    op.add_column(
        "memory_entries",
        sa.Column("embedding", ARRAY(sa.Float), nullable=True),
    )
    op.add_column(
        "memory_entries",
        sa.Column(
            "tags",
            ARRAY(sa.String),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.add_column(
        "memory_entries",
        sa.Column(
            "access_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """移除 S2 字段。"""
    op.drop_column("memory_entries", "access_count")
    op.drop_column("memory_entries", "tags")
    op.drop_column("memory_entries", "embedding")
