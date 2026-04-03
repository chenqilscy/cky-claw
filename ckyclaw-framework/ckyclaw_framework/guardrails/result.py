"""Guardrail 执行结果与异常。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuardrailResult:
    """单个 Guardrail 执行结果。"""

    tripwire_triggered: bool = False
    """是否触发 Tripwire（拦截）"""

    message: str = ""
    """说明文本（通过/拦截原因）"""


class InputGuardrailTripwireError(Exception):
    """Input Guardrail 触发 Tripwire 时抛出的异常。

    调用方可捕获此异常做后续处理（告知用户、记录日志等）。
    """

    def __init__(self, guardrail_name: str, message: str) -> None:
        self.guardrail_name = guardrail_name
        self.message = message
        super().__init__(f"Input guardrail '{guardrail_name}' tripwire triggered: {message}")


class OutputGuardrailTripwireError(Exception):
    """Output Guardrail 触发 Tripwire 时抛出的异常。

    调用方可捕获此异常做后续处理（告知用户、记录日志等）。
    """

    def __init__(self, guardrail_name: str, message: str) -> None:
        self.guardrail_name = guardrail_name
        self.message = message
        super().__init__(f"Output guardrail '{guardrail_name}' tripwire triggered: {message}")
