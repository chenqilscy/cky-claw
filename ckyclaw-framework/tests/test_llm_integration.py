"""LLM 集成测试 — 需要真实 API Key 才能运行。

标记 integration，默认 CI 中跳过。
本地运行：DEEPSEEK_API_KEY=xxx uv run pytest tests/test_llm_integration.py -v
"""

from __future__ import annotations

import os

import pytest

_HAS_KEY = bool(os.environ.get("DEEPSEEK_API_KEY"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _HAS_KEY, reason="需要 DEEPSEEK_API_KEY 环境变量"),
]


@pytest.mark.asyncio
async def test_litellm_provider_completion() -> None:
    """LiteLLMProvider 真实 LLM 调用 — 简单补全。"""
    from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
    from ckyclaw_framework.model.types import ModelSettings

    provider = LiteLLMProvider()
    settings = ModelSettings(model="deepseek/deepseek-chat", temperature=0)
    messages = [{"role": "user", "content": "回复数字42，只回复数字。"}]

    resp = await provider.get_response(
        system_instructions="你是一个精确的助手。",
        messages=messages,
        model_settings=settings,
        tools=[],
        handoffs=[],
        output_type=None,
    )

    assert resp is not None
    # 回复应包含 42
    output_text = ""
    for choice in resp.output:
        if hasattr(choice, "content"):
            output_text += choice.content or ""
    assert "42" in output_text, f"期望包含 42，实际: {output_text}"


@pytest.mark.asyncio
async def test_agent_run_simple() -> None:
    """Agent + Runner 真实端到端 — 简单问答。"""
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.runner.runner import Runner

    agent = Agent(
        name="test-simple",
        instructions="你只回复一个词：pong",
        model="deepseek/deepseek-chat",
    )
    result = await Runner.run(agent, "ping")

    assert result is not None
    assert result.final_output is not None
    assert "pong" in result.final_output.lower()


@pytest.mark.asyncio
async def test_agent_with_tool() -> None:
    """Agent + Tool 真实端到端 — 工具调用。"""
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.runner.runner import Runner
    from ckyclaw_framework.tools.function_tool import function_tool

    @function_tool
    async def add(a: int, b: int) -> int:
        """加法运算。"""
        return a + b

    agent = Agent(
        name="test-tool",
        instructions="你是数学助手，使用 add 工具回答加法问题。只返回数字结果。",
        model="deepseek/deepseek-chat",
        tools=[add],
    )
    result = await Runner.run(agent, "15 + 27 等于多少？")

    assert result is not None
    assert result.final_output is not None
    assert "42" in result.final_output


@pytest.mark.asyncio
async def test_litellm_provider_streaming() -> None:
    """LiteLLMProvider 流式输出测试。"""
    from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
    from ckyclaw_framework.model.types import ModelSettings

    provider = LiteLLMProvider()
    settings = ModelSettings(model="deepseek/deepseek-chat", temperature=0)
    messages = [{"role": "user", "content": "说出一个数字：7"}]

    chunks = []
    async for chunk in provider.get_streaming_response(
        system_instructions="你只回复数字。",
        messages=messages,
        model_settings=settings,
        tools=[],
        handoffs=[],
        output_type=None,
    ):
        chunks.append(chunk)

    assert len(chunks) > 0, "应收到至少 1 个 chunk"
