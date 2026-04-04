"""Tool Guardrail — 工具调用前后安全检测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from ckyclaw_framework.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


@dataclass
class ToolGuardrail:
    """Tool Guardrail 定义。

    与 Input/Output Guardrail 的关键区别：触发 Tripwire 时不中断整个 Run，
    而是将错误消息作为 ToolResult 返回给 LLM，让 LLM 自行决策。

    before_fn 签名: (context: RunContext, tool_name: str, arguments: dict) -> GuardrailResult
    after_fn 签名: (context: RunContext, tool_name: str, result: str) -> GuardrailResult
    """

    name: str = ""
    """Guardrail 名称（用于日志/Span）。"""

    before_fn: Callable[..., Awaitable[GuardrailResult]] | None = None
    """工具执行前检测函数。接收 (RunContext, tool_name, arguments)，返回 GuardrailResult。
    tripwire 触发时跳过工具执行，将错误消息作为 ToolResult 返回。"""

    after_fn: Callable[..., Awaitable[GuardrailResult]] | None = None
    """工具执行后检测函数。接收 (RunContext, tool_name, result)，返回 GuardrailResult。
    tripwire 触发时替换 ToolResult 为错误消息。"""

    condition: Callable[["RunContext"], bool] | None = None
    """运行时条件函数。返回 True 时启用，False 时跳过。None 表示始终启用。"""

    def __post_init__(self) -> None:
        if not self.name:
            # 尝试从 before_fn 或 after_fn 取名
            fn = self.before_fn or self.after_fn
            self.name = getattr(fn, "__name__", "unnamed_tool_guardrail") if fn else "unnamed_tool_guardrail"
