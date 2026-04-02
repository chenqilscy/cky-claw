"""Input Guardrail — 用户输入安全检测。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable

from ckyclaw_framework.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


@dataclass
class InputGuardrail:
    """Input Guardrail 定义。

    guardrail_function 签名: (context: RunContext, input_text: str) -> GuardrailResult
    """

    guardrail_function: Callable[..., Awaitable[GuardrailResult]]
    """异步检测函数。接收 (RunContext, str)，返回 GuardrailResult。"""

    name: str = ""
    """Guardrail 名称（用于日志/Span）。默认取函数名。"""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = getattr(self.guardrail_function, "__name__", "unnamed_guardrail")
