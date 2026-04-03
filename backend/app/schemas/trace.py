"""Trace/Span 响应 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpanResponse(BaseModel):
    """Span 响应。"""

    id: str
    trace_id: str
    parent_span_id: str | None = None
    type: str
    name: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: int | None = None
    input_data: dict[str, Any] | None = Field(None, alias="input")
    output_data: dict[str, Any] | None = Field(None, alias="output")
    metadata: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    token_usage: dict[str, int] | None = None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class TraceResponse(BaseModel):
    """Trace 响应。"""

    id: str
    workflow_name: str
    group_id: str | None = None
    session_id: uuid.UUID | None = None
    agent_name: str | None = None
    status: str
    span_count: int
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class TraceDetailResponse(BaseModel):
    """Trace 详情响应（含 Span 列表）。"""

    trace: TraceResponse
    spans: list[SpanResponse]


class TraceListResponse(BaseModel):
    """Trace 列表响应。"""

    items: list[TraceResponse]
    total: int


class SpanListResponse(BaseModel):
    """Span 列表响应。"""

    items: list[SpanResponse]
    total: int


class TokenUsageStats(BaseModel):
    """Token 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class SpanTypeCount(BaseModel):
    """按 Span 类型计数。"""

    agent: int = 0
    llm: int = 0
    tool: int = 0
    handoff: int = 0
    guardrail: int = 0


class GuardrailStats(BaseModel):
    """Guardrail 统计。"""

    total: int = 0
    triggered: int = 0
    trigger_rate: float = 0.0


class TraceStatsResponse(BaseModel):
    """Trace 统计响应。"""

    total_traces: int = 0
    total_spans: int = 0
    avg_duration_ms: float | None = None
    total_tokens: TokenUsageStats = Field(default_factory=TokenUsageStats)
    span_type_counts: SpanTypeCount = Field(default_factory=SpanTypeCount)
    guardrail_stats: GuardrailStats = Field(default_factory=GuardrailStats)
    error_rate: float = 0.0
