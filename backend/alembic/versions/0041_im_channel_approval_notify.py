"""im_channels: 添加 notify_approvals + approval_recipient_id 字段

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-06
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加审批通知配置列到 im_channels 表。"""
    op.add_column(
        "im_channels",
        sa.Column(
            "notify_approvals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否接收审批通知",
        ),
    )
    op.add_column(
        "im_channels",
        sa.Column(
            "approval_recipient_id",
            sa.String(128),
            nullable=True,
            comment="审批通知接收方 ID（IM 平台用户/群组标识）",
        ),
    )


def downgrade() -> None:
    """移除审批通知列。"""
    op.drop_column("im_channels", "approval_recipient_id")
    op.drop_column("im_channels", "notify_approvals")
