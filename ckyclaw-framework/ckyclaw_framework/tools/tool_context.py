"""ToolContext — 工具执行上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


@dataclass
class ToolContext:
    """工具执行时的上下文信息。"""

    run_context: RunContext
    """所属 RunContext"""

    tool_name: str = ""
    """当前工具名称"""

    tool_call_id: str = ""
    """工具调用 ID"""

    arguments: dict[str, Any] | None = None
    """工具调用参数"""
