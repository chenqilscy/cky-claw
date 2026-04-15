"""WorkflowRunConfig — 工作流运行配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.model.provider import ModelProvider


@dataclass
class WorkflowRunConfig:
    """工作流级别运行配置。"""

    model_provider: ModelProvider | None = None
    tool_timeout: float | None = None
    workflow_timeout: float | None = None
    fail_fast: bool = True
    tracing_enabled: bool = True
