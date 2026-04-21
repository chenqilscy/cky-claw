"""LLMGuardrail — 基于 LLM 的语义护栏基类。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kasaya.guardrails.result import GuardrailResult

if TYPE_CHECKING:
    from kasaya.model.provider import ModelProvider
    from kasaya.runner.run_context import RunContext

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT_TEMPLATE = """\
你是一个安全审核助手。请判断以下内容是否安全。

内容:
{content}

请用以下 JSON 格式回复（只输出 JSON，不要其他内容）:
{{"safe": true/false, "confidence": 0.0~1.0, "reason": "判断理由"}}
"""


@dataclass
class LLMGuardrail:
    """基于 LLM 的语义护栏基类。

    使用轻量 LLM 模型对内容进行语义安全判定。

    用法::

        guardrail = LLMGuardrail(
            model="gpt-4o-mini",
            prompt_template="...",
            threshold=0.8,
        )
        agent = Agent(
            input_guardrails=[InputGuardrail(guardrail_function=guardrail.as_input_fn())],
        )

    性能考虑:
    - 默认使用 gpt-4o-mini 等低延迟模型
    - 5 秒超时（超时视为通过，fail-open）
    - 可通过子类重写 prompt_template 实现特定场景
    """

    model: str = "gpt-4o-mini"
    """用于判定的 LLM 模型。建议使用低延迟模型。"""

    model_provider: ModelProvider | None = None
    """自定义模型提供商。为 None 时使用 LiteLLMProvider。"""

    prompt_template: str = _DEFAULT_PROMPT_TEMPLATE
    """Prompt 模板，必须包含 {content} 占位符。"""

    threshold: float = 0.8
    """判定阈值。confidence >= threshold 时触发 tripwire。"""

    timeout: float = 5.0
    """LLM 调用超时（秒）。超时视为通过（fail-open）。"""

    name: str = "llm_guardrail"
    """护栏名称。"""

    _provider: Any = field(default=None, init=False, repr=False)

    def _get_provider(self) -> Any:
        """延迟初始化 ModelProvider。"""
        if self.model_provider is not None:
            return self.model_provider
        if self._provider is None:
            from kasaya.model.litellm_provider import LiteLLMProvider
            self._provider = LiteLLMProvider()
        return self._provider

    async def evaluate(self, content: str) -> GuardrailResult:
        """调用 LLM 评估内容安全性。

        1. 将 content 填入 prompt_template
        2. 调用 LLM → 期望返回 JSON {safe, confidence, reason}
        3. confidence >= threshold 且 safe=false → tripwire_triggered = True
        4. 超时/解析异常 → fail-open（通过）
        """
        from kasaya.model.message import Message, MessageRole

        prompt = self.prompt_template.format(content=content)
        [Message(role=MessageRole.USER, content=prompt)]

        provider = self._get_provider()
        try:
            response = await asyncio.wait_for(
                provider.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                ),
                timeout=self.timeout,
            )
        except TimeoutError:
            logger.warning("LLMGuardrail '%s' 超时（%.1fs），fail-open", self.name, self.timeout)
            return GuardrailResult(tripwire_triggered=False, message=f"timeout ({self.timeout}s)")
        except Exception as e:
            logger.exception("LLMGuardrail '%s' 调用异常，fail-open: %s", self.name, e)
            return GuardrailResult(tripwire_triggered=False, message=f"error: {e}")

        # 解析 LLM 响应
        raw = response.content or ""
        try:
            # 尝试提取 JSON（可能被包在 ```json ... ``` 中）
            json_str = raw.strip()
            if json_str.startswith("```"):
                # 移除代码块标记
                lines = json_str.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                json_str = "\n".join(lines).strip()
            parsed = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            logger.warning("LLMGuardrail '%s' 响应解析失败，fail-open: %s", self.name, raw[:200])
            return GuardrailResult(tripwire_triggered=False, message=f"parse error: {raw[:100]}")

        safe = parsed.get("safe", True)
        confidence = float(parsed.get("confidence", 0.0))
        reason = parsed.get("reason", "")

        triggered = not safe and confidence >= self.threshold
        return GuardrailResult(
            tripwire_triggered=triggered,
            message=reason if triggered else "safe",
        )

    def as_input_fn(self) -> Any:
        """返回与 InputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx: RunContext, input_text: str) -> GuardrailResult:
            return await self.evaluate(input_text)

        _fn.__name__ = self.name
        return _fn

    def as_output_fn(self) -> Any:
        """返回与 OutputGuardrail.guardrail_function 兼容的异步函数。"""

        async def _fn(ctx: RunContext, output_text: str) -> GuardrailResult:
            return await self.evaluate(output_text)

        _fn.__name__ = self.name
        return _fn

    def as_tool_before_fn(self) -> Any:
        """返回与 ToolGuardrail.before_fn 兼容的异步函数。"""
        import json as _json

        async def _fn(ctx: RunContext, tool_name: str, arguments: dict[str, Any]) -> GuardrailResult:
            text = _json.dumps(arguments, ensure_ascii=False)
            return await self.evaluate(text)

        _fn.__name__ = self.name
        return _fn

    def as_tool_after_fn(self) -> Any:
        """返回与 ToolGuardrail.after_fn 兼容的异步函数。"""

        async def _fn(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
            return await self.evaluate(result)

        _fn.__name__ = self.name
        return _fn
