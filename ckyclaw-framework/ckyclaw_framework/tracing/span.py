"""Span — 执行步骤追踪。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class SpanType(str, Enum):
    """Span 类型。"""

    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    HANDOFF = "handoff"
    GUARDRAIL = "guardrail"


class SpanStatus(str, Enum):
    """Span 状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """执行步骤追踪。"""

    span_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = ""
    parent_span_id: str | None = None
    type: SpanType = SpanType.AGENT
    name: str = ""
    status: SpanStatus = SpanStatus.PENDING
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    token_usage: dict[str, int] | None = None
