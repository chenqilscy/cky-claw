"""provider_configs: 添加 model_tier + capabilities 字段

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 model_tier 和 capabilities 列到 provider_configs 表。"""
    op.add_column(
        "provider_configs",
        sa.Column(
            "model_tier",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'moderate'"),
            comment="模型层级: simple / moderate / complex / reasoning / multimodal",
        ),
    )
    op.add_column(
        "provider_configs",
        sa.Column(
            "capabilities",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="模型能力标签: text / code / vision / reasoning / function_calling",
        ),
    )


def downgrade() -> None:
    """移除 model_tier 和 capabilities 列。"""
    op.drop_column("provider_configs", "capabilities")
    op.drop_column("provider_configs", "model_tier")
