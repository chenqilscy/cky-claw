"""PIIDetectionGuardrail — 基于正则/模式匹配的 PII 泄露检测护栏。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


# 中国常见 PII 模式
_DEFAULT_PII_PATTERNS: dict[str, str] = {
    "phone": r"1[3-9]\d{9}",
    "id_card": r"\d{17}[\dXx]",
    "bank_card": r"\d{16,19}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
}


@dataclass
class PIIDetectionGuardrail:
    """PII（个人身份信息）泄露检测护栏。

    默认内置中国常见 PII 模式（手机号、身份证号、银行卡号、邮箱），
    可通过 patterns 参数自定义或覆盖。

    用法::

        pii = PIIDetectionGuardrail()
        agent = Agent(
            output_guardrails=[OutputGuardrail(guardrail_function=pii.as_output_fn())],
        )
    """

    patterns: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_PII_PATTERNS))
    """PII 模式字典 {名称: 正则表达式}。"""

    message: str = "检测到 PII 泄露"
    """触发时的说明消息模板。实际消息会附带匹配的 PII 类型。"""

    name: str = "pii_detection"
    """护栏名称。"""

    _compiled: dict[str, re.Pattern[str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for pii_name, pattern in self.patterns.items():
            try:
                self._compiled[pii_name] = re.compile(pattern)
            except re.error as e:
                raise ValueError(f"无效的 PII 正则表达式 '{pii_name}': {pattern} — {e}") from e

    async def check(self, text: str) -> GuardrailResult:
        """检测文本中是否包含 PII。"""
        detected: list[str] = []
        for pii_name, compiled in self._compiled.items():
            if compiled.search(text):
                detected.append(pii_name)
        if detected:
            detail = ", ".join(detected)
            return GuardrailResult(
                tripwire_triggered=True,
                message=f"{self.message}（类型: {detail}）",
            )
        return GuardrailResult(tripwire_triggered=False, message="safe")

    def as_input_fn(self) -> Any:
        """返回与 InputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx: RunContext, input_text: str) -> GuardrailResult:
            return await self.check(input_text)

        _fn.__name__ = self.name
        return _fn

    def as_output_fn(self) -> Any:
        """返回与 OutputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx: RunContext, output_text: str) -> GuardrailResult:
            return await self.check(output_text)

        _fn.__name__ = self.name
        return _fn

    def as_tool_after_fn(self) -> Any:
        """返回与 ToolGuardrail.after_fn 兼容的异步函数。"""

        async def _fn(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
            return await self.check(result)

        _fn.__name__ = self.name
        return _fn
