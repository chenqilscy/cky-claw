"""create traces and spans tables

Revision ID: 0006
Revises: 0005
Create Date: 2025-07-18

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- traces ---
    op.create_table(
        "traces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workflow_name", sa.String(128), nullable=False, server_default="default"),
        sa.Column("group_id", sa.String(64), nullable=True),
        sa.Column("session_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
        sa.Column("span_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_traces_workflow_name", "traces", ["workflow_name"])
    op.create_index("ix_traces_group_id", "traces", ["group_id"])
    op.create_index("ix_traces_session_id", "traces", ["session_id"])
    op.create_index("ix_traces_agent_name", "traces", ["agent_name"])
    op.create_index("ix_traces_start_time", "traces", ["start_time"])

    # --- spans ---
    op.create_table(
        "spans",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("parent_span_id", sa.String(64), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", pg.JSONB(), nullable=True),
        sa.Column("output", pg.JSONB(), nullable=True),
        sa.Column("metadata", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("token_usage", pg.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_parent_span_id", "spans", ["parent_span_id"])
    op.create_index("ix_spans_type", "spans", ["type"])
    op.create_index("ix_spans_start_time", "spans", ["start_time"])


def downgrade() -> None:
    op.drop_table("spans")
    op.drop_table("traces")
