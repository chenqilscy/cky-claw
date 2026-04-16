"""add knowledge graph tables

Revision ID: 0062
Revises: 0061
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. knowledge_bases 增加 mode 字段
    op.add_column(
        "knowledge_bases",
        sa.Column("mode", sa.String(16), nullable=False, server_default=sa.text("'vector'")),
    )

    # 2. 创建 knowledge_entities 表
    op.create_table(
        "knowledge_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_chunks", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("confidence_label", sa.String(16), nullable=False, server_default=sa.text("'extracted'")),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_knowledge_entities_kb_name_type",
        "knowledge_entities",
        ["knowledge_base_id", "name", "entity_type"],
    )

    # 3. 创建 knowledge_relations 表
    op.create_table(
        "knowledge_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("source_chunk", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("confidence_label", sa.String(16), nullable=False, server_default=sa.text("'inferred'")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_knowledge_relations_kb_source",
        "knowledge_relations",
        ["knowledge_base_id", "source_entity_id"],
    )
    op.create_index(
        "ix_knowledge_relations_kb_target",
        "knowledge_relations",
        ["knowledge_base_id", "target_entity_id"],
    )

    # 4. 创建 knowledge_communities 表
    op.create_table(
        "knowledge_communities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("entity_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("parent_community_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_communities.id"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("knowledge_communities")
    op.drop_index("ix_knowledge_relations_kb_target", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_kb_source", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
    op.drop_index("ix_knowledge_entities_kb_name_type", table_name="knowledge_entities")
    op.drop_table("knowledge_entities")
    op.drop_column("knowledge_bases", "mode")
