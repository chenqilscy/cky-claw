"""config_change_logs created_at 索引。

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-05
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_config_change_logs_created_at",
        "config_change_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_config_change_logs_created_at", table_name="config_change_logs")
