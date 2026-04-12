"""Add composite indexes for hot query paths.

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # token_usage: APM 仪表盘按 agent + 时间范围聚合
    op.create_index(
        "ix_token_usage_agent_ts",
        "token_usage_logs",
        ["agent_name", "timestamp"],
    )

    # traces: trace 列表按 agent + 创建时间排序
    op.create_index(
        "ix_traces_agent_created",
        "traces",
        ["agent_name", "created_at"],
    )

    # spans: span 按 trace_id + start_time 排序（waterfall 视图）
    op.create_index(
        "ix_spans_trace_start",
        "spans",
        ["trace_id", "start_time"],
    )

    # session_messages: 消息按 session + 创建时间排序
    op.create_index(
        "ix_session_messages_sess_created",
        "session_messages",
        ["session_id", "created_at"],
    )

    # benchmark_runs: 按 suite + 创建时间
    op.create_index(
        "ix_benchmark_runs_suite_created",
        "benchmark_runs",
        ["suite_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_benchmark_runs_suite_created", table_name="benchmark_runs")
    op.drop_index("ix_session_messages_sess_created", table_name="session_messages")
    op.drop_index("ix_spans_trace_start", table_name="spans")
    op.drop_index("ix_traces_agent_created", table_name="traces")
    op.drop_index("ix_token_usage_agent_ts", table_name="token_usage_logs")
