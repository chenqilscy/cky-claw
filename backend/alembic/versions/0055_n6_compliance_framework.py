"""N6: Compliance tables — classification labels, retention policies, erasure requests, control points.

Revision ID: 0055
Revises: 0054
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum types
    data_classification_enum = postgresql.ENUM(
        "public", "internal", "sensitive", "pii", "phi",
        name="data_classification_enum", create_type=False,
    )
    retention_status_enum = postgresql.ENUM(
        "active", "expired", "deleted",
        name="retention_status_enum", create_type=False,
    )
    erasure_status_enum = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="erasure_status_enum", create_type=False,
    )
    data_classification_enum.create(op.get_bind(), checkfirst=True)
    retention_status_enum.create(op.get_bind(), checkfirst=True)
    erasure_status_enum.create(op.get_bind(), checkfirst=True)

    # data_classification_labels
    op.create_table(
        "data_classification_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(64), nullable=False, index=True),
        sa.Column("resource_id", sa.String(128), nullable=False, index=True),
        sa.Column("classification", data_classification_enum, nullable=False, server_default="internal"),
        sa.Column("auto_detected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(64), nullable=False, index=True),
        sa.Column("classification", data_classification_enum, nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("status", retention_status_enum, nullable=False, server_default="active"),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # erasure_requests
    op.create_table(
        "erasure_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", erasure_status_enum, nullable=False, server_default="pending", index=True),
        sa.Column("scanned_resources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_resources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # compliance_control_points
    op.create_table(
        "compliance_control_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("control_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("implementation", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_links", postgresql.JSONB(), nullable=True),
        sa.Column("is_satisfied", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("compliance_control_points")
    op.drop_table("erasure_requests")
    op.drop_table("retention_policies")
    op.drop_table("data_classification_labels")
    op.execute("DROP TYPE IF EXISTS erasure_status_enum")
    op.execute("DROP TYPE IF EXISTS retention_status_enum")
    op.execute("DROP TYPE IF EXISTS data_classification_enum")
