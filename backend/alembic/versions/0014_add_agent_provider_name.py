"""AgentConfig 新增 provider_name 字段。

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("provider_name", sa.String(64), nullable=True),
    )
    op.create_index("idx_agent_configs_provider_name", "agent_configs", ["provider_name"])


def downgrade() -> None:
    op.drop_index("idx_agent_configs_provider_name", table_name="agent_configs")
    op.drop_column("agent_configs", "provider_name")
