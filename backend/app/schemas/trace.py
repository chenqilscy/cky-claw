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
