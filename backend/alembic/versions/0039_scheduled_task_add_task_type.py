"""scheduled_task: 添加 task_type 字段

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_tasks",
        sa.Column(
            "task_type",
            sa.String(32),
            server_default="agent_run",
            nullable=False,
            comment="任务类型: agent_run / evolution_analyze",
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "task_type")
