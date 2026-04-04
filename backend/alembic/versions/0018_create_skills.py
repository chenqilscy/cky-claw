"""创建技能知识包表 skills。

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("version", sa.String(32), nullable=False, server_default=sa.text("'1.0.0'")),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(16), nullable=False, server_default=sa.text("'custom'")),
        sa.Column("tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("applicable_agents", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("author", sa.String(64), nullable=False, server_default=sa.text("''")),
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
    op.create_index("idx_skill_name", "skills", ["name"], unique=True)
    op.create_index("idx_skill_category", "skills", ["category"])


def downgrade() -> None:
    op.drop_index("idx_skill_category", table_name="skills")
    op.drop_index("idx_skill_name", table_name="skills")
    op.drop_table("skills")
