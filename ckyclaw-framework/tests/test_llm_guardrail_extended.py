"""LLMGuardrail 扩展测试 — 覆盖 as_tool_before_fn / as_tool_after_fn / _get_provider 等路径。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ckyclaw_framework.guardrails.llm_guardrail import LLMGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult
from ckyclaw_framework.model.message import TokenUsage
from ckyclaw_framework.model.provider import ModelProvider, ModelResponse
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext


def _make_ctx() -> RunContext:
    from ckyclaw_framework.agent.agent import Agent
    return RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)


class _UnsafeProvider(ModelProvider):
    async def chat(self, **kwargs: Any) -> ModelResponse:
        return ModelResponse(
            content='{"safe": false, "confidence": 0.95, "reason": "harmful"}',
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


class _SafeProvider(ModelProvider):
    async def chat(self, **kwargs: Any) -> ModelResponse:
        return ModelResponse(
            content='{"safe": true, "confidence": 0.1, "reason": "ok"}',
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


# ═══════════════════════════════════════════════════════════════════
# as_tool_before_fn — JSON 序列化参数后进行 LLM 评估
# ═══════════════════════════════════════════════════════════════════


class TestLLMGuardrailToolBeforeFn:

    @pytest.mark.asyncio
    async def test_tool_before_fn_triggered(self) -> None:
        """工具参数被 JSON 化后触发 LLM 判定。"""
        g = LLMGuardrail(model_provider=_UnsafeProvider(), name="tool_before")
        fn = g.as_tool_before_fn()
        ctx = _make_ctx()
        r = await fn(ctx, "dangerous_tool", {"action": "delete_all"})
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_tool_before_fn_safe(self) -> None:
        g = LLMGuardrail(model_provider=_SafeProvider(), name="tool_before_safe")
        fn = g.as_tool_before_fn()
        ctx = _make_ctx()
        r = await fn(ctx, "search", {"query": "weather"})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_tool_before_fn_name(self) -> None:
        g = LLMGuardrail(name="my_llm_guard")
        fn = g.as_tool_before_fn()
        assert fn.__name__ == "my_llm_guard"


# ═══════════════════════════════════════════════════════════════════
# as_tool_after_fn — 工具返回值 LLM 评估
# ═══════════════════════════════════════════════════════════════════


class TestLLMGuardrailToolAfterFn:

    @pytest.mark.asyncio
    async def test_tool_after_fn_triggered(self) -> None:
        g = LLMGuardrail(model_provider=_UnsafeProvider(), name="tool_after")
        fn = g.as_tool_after_fn()
        ctx = _make_ctx()
        r = await fn(ctx, "search", "Harmful content returned")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_tool_after_fn_safe(self) -> None:
        g = LLMGuardrail(model_provider=_SafeProvider(), name="tool_after_safe")
        fn = g.as_tool_after_fn()
        ctx = _make_ctx()
        r = await fn(ctx, "search", "Safe result")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_tool_after_fn_name(self) -> None:
        g = LLMGuardrail(name="after_guard")
        fn = g.as_tool_after_fn()
        assert fn.__name__ == "after_guard"


# ═══════════════════════════════════════════════════════════════════
# _get_provider — 延迟初始化
# ═══════════════════════════════════════════════════════════════════


class TestLLMGuardrailGetProvider:

    def test_custom_provider_returned(self) -> None:
        """指定 model_provider 时直接返回。"""
        provider = _SafeProvider()
        g = LLMGuardrail(model_provider=provider)
        assert g._get_provider() is provider

    def test_default_provider_created(self) -> None:
        """未指定 model_provider 时创建 LiteLLMProvider。"""
        g = LLMGuardrail()
        p1 = g._get_provider()
        p2 = g._get_provider()
        # 同一实例（缓存）
        assert p1 is p2


# ═══════════════════════════════════════════════════════════════════
# evaluate 响应无 content
# ═══════════════════════════════════════════════════════════════════


class TestLLMGuardrailEmptyResponse:

    @pytest.mark.asyncio
    async def test_none_content_fail_open(self) -> None:
        """LLM 返回空 content 时 fail-open。"""

        class _NoneContentProvider(ModelProvider):
            async def chat(self, **kwargs: Any) -> ModelResponse:
                return ModelResponse(
                    content=None,
                    tool_calls=[],
                    token_usage=TokenUsage(0, 0, 0),
                )

        g = LLMGuardrail(model_provider=_NoneContentProvider(), name="none_content")
        r = await g.evaluate("test")
        assert r.tripwire_triggered is False
        assert "parse error" in r.message

    @pytest.mark.asyncio
    async def test_safe_with_missing_fields(self) -> None:
        """JSON 缺少 confidence/reason 字段时使用默认值。"""

        class _MinimalProvider(ModelProvider):
            async def chat(self, **kwargs: Any) -> ModelResponse:
                return ModelResponse(
                    content='{"safe": true}',
                    tool_calls=[],
                    token_usage=TokenUsage(0, 0, 0),
                )

        g = LLMGuardrail(model_provider=_MinimalProvider())
        r = await g.evaluate("test")
        assert r.tripwire_triggered is False
