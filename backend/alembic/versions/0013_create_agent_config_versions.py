"""创建 agent_config_versions 表。

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_config_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_config_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("change_summary", sa.String(512), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_agent_config_versions_agent_id", "agent_config_versions", ["agent_config_id"])
    op.create_index("idx_agent_config_versions_created_at", "agent_config_versions", ["created_at"])
    op.create_unique_constraint("uq_agent_version", "agent_config_versions", ["agent_config_id", "version"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_version", "agent_config_versions", type_="unique")
    op.drop_index("idx_agent_config_versions_created_at", table_name="agent_config_versions")
    op.drop_index("idx_agent_config_versions_agent_id", table_name="agent_config_versions")
    op.drop_table("agent_config_versions")
