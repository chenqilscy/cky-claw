"""RegexGuardrail — 基于正则表达式/关键词的安全护栏。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ckyclaw_framework.guardrails.result import GuardrailResult


@dataclass
class RegexGuardrail:
    """正则表达式护栏。

    支持两种模式：
    - patterns: 正则表达式列表，任一匹配即触发
    - keywords: 关键词列表，任一出现即触发（内部转为正则）

    当两者同时指定时，先检测 patterns，再检测 keywords。
    """

    patterns: list[str] = field(default_factory=list)
    """正则表达式列表（任一匹配即 tripwire）。"""

    keywords: list[str] = field(default_factory=list)
    """关键词列表（大小写不敏感，任一出现即 tripwire）。"""

    message: str = "输入被安全规则拦截"
    """触发时的说明消息。"""

    name: str = "regex_guardrail"
    """护栏名称。"""

    case_sensitive: bool = False
    """正则匹配是否大小写敏感。"""

    _compiled_patterns: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        flags = 0 if self.case_sensitive else re.IGNORECASE
        for pattern in self.patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, flags))
            except re.error as e:
                raise ValueError(f"无效的正则表达式 '{pattern}': {e}") from e
        for keyword in self.keywords:
            escaped = re.escape(keyword)
            self._compiled_patterns.append(re.compile(escaped, flags))

    async def check(self, text: str) -> GuardrailResult:
        """检测文本是否触发护栏。"""
        for compiled in self._compiled_patterns:
            if compiled.search(text):
                return GuardrailResult(
                    tripwire_triggered=True,
                    message=self.message,
                )
        return GuardrailResult(tripwire_triggered=False, message="safe")

    def as_input_fn(self):
        """返回与 InputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx, input_text: str) -> GuardrailResult:
            return await self.check(input_text)

        _fn.__name__ = self.name
        return _fn

    def as_output_fn(self):
        """返回与 OutputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx, output_text: str) -> GuardrailResult:
            return await self.check(output_text)

        _fn.__name__ = self.name
        return _fn
