"""create roles and add role_id to users

Revision ID: 0023
Revises: 0022
Create Date: 2025-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 roles 表
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("description", sa.String(256), nullable=False, server_default=sa.text("''")),
        sa.Column("permissions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 给 users 表添加 role_id 外键列
    op.add_column("users", sa.Column("role_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_column("users", "role_id")
    op.drop_table("roles")
