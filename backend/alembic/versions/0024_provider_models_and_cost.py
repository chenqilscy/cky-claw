"""provider_models 表 + token_usage 成本字段

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 provider_models 表
    op.create_table(
        "provider_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("provider_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("context_window", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_price_per_1k", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("completion_price_per_1k", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # token_usage_logs 添加成本字段
    op.add_column("token_usage_logs", sa.Column("prompt_cost", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("token_usage_logs", sa.Column("completion_cost", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("token_usage_logs", sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"))


def downgrade() -> None:
    op.drop_column("token_usage_logs", "total_cost")
    op.drop_column("token_usage_logs", "completion_cost")
    op.drop_column("token_usage_logs", "prompt_cost")
    op.drop_table("provider_models")
