"""N5: Marketplace — AgentTemplate 扩展字段 + marketplace_reviews 表。

Revision ID: 0054
Revises: 0053
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 Marketplace 字段和评论表。"""
    # AgentTemplate 扩展字段
    op.add_column("agent_templates", sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("agent_templates", sa.Column("downloads", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("agent_templates", sa.Column("rating", sa.Float(), nullable=False, server_default=sa.text("0.0")))
    op.add_column("agent_templates", sa.Column("rating_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("agent_templates", sa.Column("author_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True))
    op.create_index("ix_agent_templates_published", "agent_templates", ["published"])
    op.create_index("ix_agent_templates_author_org_id", "agent_templates", ["author_org_id"])

    # MarketplaceReview 表
    op.create_table(
        "marketplace_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_templates.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # 唯一约束：每个用户对每个模板只能评一次
    op.create_unique_constraint("uq_review_user_template", "marketplace_reviews", ["user_id", "template_id"])


def downgrade() -> None:
    """移除 Marketplace 字段和评论表。"""
    op.drop_constraint("uq_review_user_template", "marketplace_reviews", type_="unique")
    op.drop_table("marketplace_reviews")
    op.drop_index("ix_agent_templates_author_org_id", table_name="agent_templates")
    op.drop_index("ix_agent_templates_published", table_name="agent_templates")
    op.drop_column("agent_templates", "author_org_id")
    op.drop_column("agent_templates", "rating_count")
    op.drop_column("agent_templates", "rating")
    op.drop_column("agent_templates", "downloads")
    op.drop_column("agent_templates", "published")
