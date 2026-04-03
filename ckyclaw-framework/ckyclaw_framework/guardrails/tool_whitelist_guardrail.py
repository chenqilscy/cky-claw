"""ToolWhitelistGuardrail — 工具白名单护栏。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ckyclaw_framework.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext


@dataclass
class ToolWhitelistGuardrail:
    """工具白名单护栏。

    仅允许白名单中的工具调用，未列入的工具将被拦截。

    用法::

        guard = ToolWhitelistGuardrail(allowed_tools=["search", "calculator"])
        agent = Agent(
            tool_guardrails=[ToolGuardrail(name="whitelist", before_fn=guard.as_before_fn())],
        )
    """

    allowed_tools: list[str] = field(default_factory=list)
    """允许调用的工具名称列表。"""

    message: str = "工具不在白名单中"
    """触发时的说明消息。"""

    name: str = "tool_whitelist"
    """护栏名称。"""

    _allowed_set: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self._allowed_set = set(self.allowed_tools)

    def as_before_fn(self):
        """返回与 ToolGuardrail.before_fn 兼容的异步函数。"""

        async def _fn(ctx: RunContext, tool_name: str, arguments: dict) -> GuardrailResult:
            if tool_name in self._allowed_set:
                return GuardrailResult(tripwire_triggered=False, message="allowed")
            return GuardrailResult(
                tripwire_triggered=True,
                message=f"{self.message}：'{tool_name}'",
            )

        _fn.__name__ = self.name
        return _fn
