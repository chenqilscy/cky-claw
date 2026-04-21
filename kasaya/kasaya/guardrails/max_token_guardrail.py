"""MaxTokenGuardrail — 输入长度限制护栏。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kasaya.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from kasaya.runner.run_context import RunContext


@dataclass
class MaxTokenGuardrail:
    """输入 Token 数量限制护栏。

    通过字符数估算 Token 数量（中文约 2 字符/token，英文约 4 字符/token），
    超过阈值时触发 Tripwire。

    用法::

        guard = MaxTokenGuardrail(max_tokens=4096)
        agent = Agent(
            input_guardrails=[InputGuardrail(guardrail_function=guard.as_input_fn())],
        )
    """

    max_tokens: int = 4096
    """最大 Token 数量。"""

    chars_per_token: float = 2.5
    """字符数/Token 的估算比例（中英混合取 2.5）。"""

    message: str = "输入过长"
    """触发时的说明消息。"""

    name: str = "max_token"
    """护栏名称。"""

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 Token 数量。"""
        return max(1, int(len(text) / self.chars_per_token))

    async def check(self, text: str) -> GuardrailResult:
        """检测文本长度是否超限。"""
        estimated = self._estimate_tokens(text)
        if estimated > self.max_tokens:
            return GuardrailResult(
                tripwire_triggered=True,
                message=f"{self.message}（估算 {estimated} tokens，限制 {self.max_tokens}）",
            )
        return GuardrailResult(tripwire_triggered=False, message="safe")

    def as_input_fn(self) -> Any:
        """返回与 InputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx: RunContext, input_text: str) -> GuardrailResult:
            return await self.check(input_text)

        _fn.__name__ = self.name
        return _fn
