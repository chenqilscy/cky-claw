"""Trace — 完整执行链路追踪。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from ckyclaw_framework.tracing.span import Span


@dataclass
class Trace:
    """一次完整执行的链路追踪。"""

    trace_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_name: str = "default"
    group_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
