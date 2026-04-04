"""Dynamic Instructions + Handoff input_type + Runner 重试机制测试。"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import Runner, _build_system_message, _build_tool_schemas


# ── Mock Provider ────────────────────────────────────────────────


class MockProvider(ModelProvider):
    """可编排的 Mock LLM 提供商。"""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        if stream:
            return self._stream_response()
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return resp

    async def _stream_response(self) -> AsyncIterator[ModelChunk]:
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        if resp.content:
            yield ModelChunk(content=resp.content)
        yield ModelChunk(finish_reason="stop")


class FailThenSucceedProvider(ModelProvider):
    """前 N 次调用抛异常，之后返回成功。"""

    def __init__(self, fail_count: int, success_response: ModelResponse) -> None:
        self._fail_count = fail_count
        self._success = success_response
        self._call_count = 0

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise ConnectionError(f"Simulated failure #{self._call_count}")
        return self._success


# ══════════════════════════════════════════════════════════════════
# Dynamic Instructions 测试
# ══════════════════════════════════════════════════════════════════


class TestDynamicInstructions:
    """Dynamic Instructions: str / sync callable / async callable。"""

    @pytest.mark.asyncio
    async def test_static_instructions(self) -> None:
        """静态字符串 instructions 正常工作。"""
        agent = Agent(name="static", instructions="You are helpful.")
        run_ctx = RunContext(agent=agent, config=RunConfig())
        msg = await _build_system_message(agent, run_ctx)
        assert msg.content == "You are helpful."

    @pytest.mark.asyncio
    async def test_sync_callable_instructions(self) -> None:
        """同步 callable instructions 正常工作。"""

        def dynamic_fn(ctx: RunContext) -> str:
            return f"Turn {ctx.turn_count}: be helpful."

        agent = Agent(name="sync-dyn", instructions=dynamic_fn)
        run_ctx = RunContext(agent=agent, config=RunConfig(), turn_count=3)
        msg = await _build_system_message(agent, run_ctx)
        assert msg.content == "Turn 3: be helpful."

    @pytest.mark.asyncio
    async def test_async_callable_instructions(self) -> None:
        """异步 callable instructions 正常工作。"""

        async def async_fn(ctx: RunContext) -> str:
            await asyncio.sleep(0)  # 模拟异步操作
            return f"Async turn {ctx.turn_count}: be helpful."

        agent = Agent(name="async-dyn", instructions=async_fn)
        run_ctx = RunContext(agent=agent, config=RunConfig(), turn_count=5)
        msg = await _build_system_message(agent, run_ctx)
        assert msg.content == "Async turn 5: be helpful."

    @pytest.mark.asyncio
    async def test_dynamic_instructions_with_context(self) -> None:
        """Dynamic Instructions 可以读取 RunContext.context 自定义数据。"""

        def ctx_fn(ctx: RunContext) -> str:
            lang = ctx.context.get("language", "en")
            return f"Reply in {lang}."

        agent = Agent(name="ctx-dyn", instructions=ctx_fn)
        run_ctx = RunContext(agent=agent, config=RunConfig(), context={"language": "zh"})
        msg = await _build_system_message(agent, run_ctx)
        assert msg.content == "Reply in zh."

    @pytest.mark.asyncio
    async def test_async_instructions_in_runner(self) -> None:
        """异步 Dynamic Instructions 在完整 Runner.run() 中工作。"""

        async def async_instructions(ctx: RunContext) -> str:
            return "You are an assistant that always says OK."

        agent = Agent(name="async-runner", instructions=async_instructions)
        provider = MockProvider([
            ModelResponse(content="OK", token_usage=TokenUsage(10, 5, 15)),
        ])
        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider),
        )
        assert result.output == "OK"

    @pytest.mark.asyncio
    async def test_empty_instructions(self) -> None:
        """空 instructions 返回空字符串。"""
        agent = Agent(name="empty")
        run_ctx = RunContext(agent=agent, config=RunConfig())
        msg = await _build_system_message(agent, run_ctx)
        assert msg.content == ""


# ══════════════════════════════════════════════════════════════════
# Handoff input_type 测试
# ══════════════════════════════════════════════════════════════════


class TestHandoffInputType:
    """Handoff input_type: LLM 在 Handoff 时携带结构化参数。"""

    def test_handoff_without_input_type(self) -> None:
        """无 input_type 时 Handoff 工具 schema 参数为空。"""
        target = Agent(name="target", description="Target agent")
        handoff = Handoff(agent=target)
        agent = Agent(name="source", handoffs=[handoff])
        schemas = _build_tool_schemas(agent)
        assert len(schemas) == 1
        params = schemas[0]["function"]["parameters"]
        assert params == {"type": "object", "properties": {}}

    def test_handoff_with_input_type(self) -> None:
        """设置 input_type 后 Handoff 工具 schema 包含结构化参数。"""
        from pydantic import BaseModel

        class HandoffInput(BaseModel):
            reason: str
            priority: int = 1

        target = Agent(name="target", description="Target agent")
        handoff = Handoff(agent=target, input_type=HandoffInput)
        agent = Agent(name="source", handoffs=[handoff])
        schemas = _build_tool_schemas(agent)
        assert len(schemas) == 1
        params = schemas[0]["function"]["parameters"]
        assert params["type"] == "object"
        assert "reason" in params["properties"]
        assert "priority" in params["properties"]
        # reason 是必填
        assert "reason" in params.get("required", [])

    def test_handoff_input_type_plain_agent(self) -> None:
        """直接传 Agent（非 Handoff 实例）时无 input_type。"""
        target = Agent(name="target", description="Target agent")
        agent = Agent(name="source", handoffs=[target])
        schemas = _build_tool_schemas(agent)
        assert len(schemas) == 1
        params = schemas[0]["function"]["parameters"]
        assert params == {"type": "object", "properties": {}}

    def test_handoff_input_type_schema_correctness(self) -> None:
        """验证 input_type 生成的 JSON Schema 结构完整性。"""
        from pydantic import BaseModel, Field

        class TransferMeta(BaseModel):
            reason: str = Field(description="Why transfer")
            urgency: str = Field(default="normal", description="Level")

        target = Agent(name="specialist", description="Specialist")
        handoff = Handoff(agent=target, input_type=TransferMeta)
        agent = Agent(name="triage", handoffs=[handoff])
        schemas = _build_tool_schemas(agent)
        fn_schema = schemas[0]["function"]
        assert fn_schema["name"] == "transfer_to_specialist"
        props = fn_schema["parameters"]["properties"]
        assert "reason" in props
        assert "urgency" in props

    @pytest.mark.asyncio
    async def test_handoff_with_input_type_runner(self) -> None:
        """Handoff input_type 在 Runner 中正确触发移交。"""
        from pydantic import BaseModel

        class HandoffInput(BaseModel):
            reason: str

        target = Agent(name="target", description="Target agent")
        handoff = Handoff(agent=target, input_type=HandoffInput)
        source = Agent(name="source", handoffs=[handoff])

        provider = MockProvider([
            # Source agent → handoff tool call with arguments
            ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="transfer_to_target", arguments='{"reason":"urgent"}')],
            ),
            # Target agent → final reply
            ModelResponse(content="I am target", token_usage=TokenUsage(10, 5, 15)),
        ])
        result = await Runner.run(
            source, "Help",
            config=RunConfig(model_provider=provider),
        )
        assert result.output == "I am target"
        assert result.last_agent_name == "target"


# ══════════════════════════════════════════════════════════════════
# Runner 重试机制测试
# ══════════════════════════════════════════════════════════════════


class TestRunnerRetry:
    """Runner LLM 调用失败重试。"""

    @pytest.mark.asyncio
    async def test_no_retry_by_default(self) -> None:
        """默认 max_retries=0，失败不重试。"""
        provider = FailThenSucceedProvider(
            fail_count=1,
            success_response=ModelResponse(content="OK", token_usage=TokenUsage(10, 5, 15)),
        )
        agent = Agent(name="test")
        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider, max_retries=0),
        )
        # 应失败
        assert "Error" in str(result.output)
        assert provider._call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success(self) -> None:
        """重试后成功。"""
        provider = FailThenSucceedProvider(
            fail_count=2,
            success_response=ModelResponse(content="Success!", token_usage=TokenUsage(10, 5, 15)),
        )
        agent = Agent(name="retry-test")
        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider, max_retries=3, retry_delay=0.01),
        )
        assert result.output == "Success!"
        assert provider._call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_retry_all_fail(self) -> None:
        """所有重试都失败时返回错误。"""
        provider = FailThenSucceedProvider(
            fail_count=10,  # 永远失败
            success_response=ModelResponse(content="Never"),
        )
        agent = Agent(name="fail-test")
        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider, max_retries=2, retry_delay=0.01),
        )
        assert "Error" in str(result.output)
        assert provider._call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self) -> None:
        """验证指数退避延迟。"""
        delays: list[float] = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds: float) -> None:
            delays.append(seconds)
            # 不实际等待
            return

        provider = FailThenSucceedProvider(
            fail_count=3,
            success_response=ModelResponse(content="OK", token_usage=TokenUsage(10, 5, 15)),
        )
        agent = Agent(name="backoff-test")

        with patch("ckyclaw_framework.runner.runner.asyncio.sleep", side_effect=mock_sleep):
            result = await Runner.run(
                agent, "Hello",
                config=RunConfig(model_provider=provider, max_retries=3, retry_delay=1.0),
            )

        assert result.output == "OK"
        # 3 failures → 3 sleep calls: 1.0, 2.0, 4.0
        assert len(delays) == 3
        assert delays[0] == pytest.approx(1.0)
        assert delays[1] == pytest.approx(2.0)
        assert delays[2] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_retry_config_defaults(self) -> None:
        """RunConfig 重试默认值。"""
        config = RunConfig()
        assert config.max_retries == 0
        assert config.retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_retry_with_single_retry(self) -> None:
        """单次重试成功。"""
        provider = FailThenSucceedProvider(
            fail_count=1,
            success_response=ModelResponse(content="Recovered", token_usage=TokenUsage(10, 5, 15)),
        )
        agent = Agent(name="single-retry")
        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider, max_retries=1, retry_delay=0.01),
        )
        assert result.output == "Recovered"
        assert provider._call_count == 2
