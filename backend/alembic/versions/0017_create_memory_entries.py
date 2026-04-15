"""创建记忆条目表 memory_entries。

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("agent_name", sa.String(64), nullable=True),
        sa.Column("source_session_id", sa.String(128), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_memory_user_id", "memory_entries", ["user_id"])
    op.create_index("idx_memory_type", "memory_entries", ["type"])
    op.create_index("idx_memory_agent_name", "memory_entries", ["agent_name"])
    op.create_index("idx_memory_user_type", "memory_entries", ["user_id", "type"])


def downgrade() -> None:
    op.drop_index("idx_memory_user_type", table_name="memory_entries")
    op.drop_index("idx_memory_agent_name", table_name="memory_entries")
    op.drop_index("idx_memory_type", table_name="memory_entries")
    op.drop_index("idx_memory_user_id", table_name="memory_entries")
    op.drop_table("memory_entries")
