"""F8 为 agent_configs 添加 prompt_variables 字段。

Revision ID: 0050
Revises: 0049
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 prompt_variables JSONB 列。"""
    op.add_column(
        "agent_configs",
        sa.Column(
            "prompt_variables",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Prompt 模板变量定义列表",
        ),
    )


def downgrade() -> None:
    """移除 prompt_variables 列。"""
    op.drop_column("agent_configs", "prompt_variables")
