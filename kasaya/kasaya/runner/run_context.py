"""RunContext — 执行上下文，贯穿整个 Agent Loop。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kasaya.agent.agent import Agent
    from kasaya.runner.run_config import RunConfig
    from kasaya.tracing.trace import Trace


@dataclass
class RunContext:
    """执行上下文，在 Agent Loop 中传递给工具和护栏。"""

    agent: Agent
    """当前执行的 Agent"""

    config: RunConfig
    """运行时配置"""

    trace: Trace | None = None
    """当前 Trace"""

    context: dict[str, Any] = field(default_factory=dict)
    """用户自定义上下文（透传给工具函数）"""

    turn_count: int = 0
    """当前轮次"""
