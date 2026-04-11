"""S7 创建 mailbox_messages 表，支持 Agent 间通信。

Revision ID: 0049
Revises: 0048
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 mailbox_messages 表。"""
    op.create_table(
        "mailbox_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="消息唯一标识",
        ),
        sa.Column(
            "run_id",
            sa.String(64),
            nullable=False,
            index=True,
            comment="所属运行 ID",
        ),
        sa.Column(
            "from_agent",
            sa.String(128),
            nullable=False,
            comment="发送方 Agent 名称",
        ),
        sa.Column(
            "to_agent",
            sa.String(128),
            nullable=False,
            index=True,
            comment="接收方 Agent 名称",
        ),
        sa.Column(
            "content",
            sa.String,
            nullable=False,
            server_default=sa.text("''"),
            comment="消息内容",
        ),
        sa.Column(
            "message_type",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'handoff'"),
            comment="消息类型",
        ),
        sa.Column(
            "is_read",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
            comment="是否已读",
        ),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="扩展元数据",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="创建时间",
        ),
    )


def downgrade() -> None:
    """删除 mailbox_messages 表。"""
    op.drop_table("mailbox_messages")
