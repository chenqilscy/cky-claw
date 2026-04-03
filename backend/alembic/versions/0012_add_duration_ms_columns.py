"""为 traces 和 spans 表添加 duration_ms 列。

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("traces", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("spans", sa.Column("duration_ms", sa.Integer(), nullable=True))
    # 索引便于按耗时筛选
    op.create_index("idx_traces_duration", "traces", ["duration_ms"])
    op.create_index("idx_spans_duration", "spans", ["duration_ms"])
    op.create_index("idx_spans_type_status", "spans", ["type", "status"])


def downgrade() -> None:
    op.drop_index("idx_spans_type_status", table_name="spans")
    op.drop_index("idx_spans_duration", table_name="spans")
    op.drop_index("idx_traces_duration", table_name="traces")
    op.drop_column("spans", "duration_ms")
    op.drop_column("traces", "duration_ms")
