"""Output Guardrail — Agent 输出内容安全检测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

from ckyclaw_framework.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


@dataclass
class OutputGuardrail:
    """Output Guardrail 定义。

    guardrail_function 签名: (context: RunContext, output_text: str) -> GuardrailResult

    在 LLM 返回 final_output（无 tool_calls）后、构建 RunResult 前执行。
    按列表顺序依次执行，首个 Tripwire 触发后短路中断。
    """

    guardrail_function: Callable[..., Awaitable[GuardrailResult]]
    """异步检测函数。接收 (RunContext, str)，返回 GuardrailResult。"""

    name: str = ""
    """Guardrail 名称（用于日志/Span）。默认取函数名。"""

    condition: Callable[["RunContext"], bool] | None = None
    """运行时条件函数。返回 True 时启用，False 时跳过。None 表示始终启用。"""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = getattr(self.guardrail_function, "__name__", "unnamed_output_guardrail")
