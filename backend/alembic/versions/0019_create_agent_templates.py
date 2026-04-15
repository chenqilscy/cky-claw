"""创建 Agent 模板表 agent_templates。

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("category", sa.String(32), nullable=False, server_default=sa.text("'general'")),
        sa.Column("icon", sa.String(64), nullable=False, server_default=sa.text("'RobotOutlined'")),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.text("false")),
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
    op.create_index("idx_agent_template_name", "agent_templates", ["name"], unique=True)
    op.create_index("idx_agent_template_category", "agent_templates", ["category"])


def downgrade() -> None:
    op.drop_index("idx_agent_template_category", table_name="agent_templates")
    op.drop_index("idx_agent_template_name", table_name="agent_templates")
    op.drop_table("agent_templates")
