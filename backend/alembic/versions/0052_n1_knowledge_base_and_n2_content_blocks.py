"""N1 知识库表 + N2 session_messages.content_blocks 字段。

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建知识库相关表并扩展 session_messages。"""
    op.create_table(
        "knowledge_bases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("embedding_model", sa.String(128), nullable=False, server_default=sa.text("'hash-embedding-v1'")),
        sa.Column("chunk_strategy", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_knowledge_bases_name", "knowledge_bases", ["name"], unique=False)
    op.create_index("ix_knowledge_bases_org_id", "knowledge_bases", ["org_id"], unique=False)
    op.create_index("ix_knowledge_bases_is_deleted", "knowledge_bases", ["is_deleted"], unique=False)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "knowledge_base_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False, server_default=sa.text("'text/plain'")),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'indexed'")),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_knowledge_documents_knowledge_base_id", "knowledge_documents", ["knowledge_base_id"], unique=False)
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"], unique=False)
    op.create_index("ix_knowledge_documents_is_deleted", "knowledge_documents", ["is_deleted"], unique=False)

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "knowledge_base_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", ARRAY(sa.Float()), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_knowledge_chunks_knowledge_base_id", "knowledge_chunks", ["knowledge_base_id"], unique=False)
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"], unique=False)
    op.create_index("ix_knowledge_chunks_is_deleted", "knowledge_chunks", ["is_deleted"], unique=False)

    op.add_column("session_messages", sa.Column("content_blocks", JSONB, nullable=True))


def downgrade() -> None:
    """回滚知识库表和 session_messages 扩展字段。"""
    op.drop_column("session_messages", "content_blocks")

    op.drop_index("ix_knowledge_chunks_is_deleted", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_knowledge_base_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("ix_knowledge_documents_is_deleted", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_knowledge_base_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_knowledge_bases_is_deleted", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_org_id", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_name", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
