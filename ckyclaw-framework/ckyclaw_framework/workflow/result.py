"""WorkflowResult — 工作流执行结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ckyclaw_framework.tracing.trace import Trace
from ckyclaw_framework.workflow.step import StepStatus


class WorkflowStatus(str, Enum):
    """工作流执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """单步骤执行结果。"""

    step_id: str
    status: StepStatus
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


@dataclass
class WorkflowResult:
    """工作流执行结果。"""

    workflow_name: str
    status: WorkflowStatus
    context: dict[str, Any] = field(default_factory=dict)
    step_results: dict[str, StepResult] = field(default_factory=dict)
    trace: Trace | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None
