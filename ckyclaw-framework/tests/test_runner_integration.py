"""Runner.run / run_sync 集成单元测试 — 覆盖 Agent Loop / 重试 / max_turns / session / hooks / 结构化输出。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelResponse, ToolCall
from ckyclaw_framework.runner.hooks import RunHooks
from ckyclaw_framework.runner.result import RunResult
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import FunctionTool


class SampleOutput(BaseModel):
    """测试用结构化输出。"""
    answer: str


def _mock_provider(responses: list[ModelResponse]) -> MagicMock:
    """创建可依次返回多个 response 的 mock provider。"""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=responses)
    return provider


def _text_response(content: str) -> ModelResponse:
    """创建纯文本响应（无 tool_calls）。"""
    return ModelResponse(
        content=content,
        tool_calls=[],
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_response(tool_calls: list[ToolCall], content: str = "") -> ModelResponse:
    """创建工具调用响应。"""
    return ModelResponse(
        content=content,
        tool_calls=tool_calls,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _make_tool(name: str = "my_tool", result: str = "tool_result") -> FunctionTool:
    """创建简单工具。"""
    async def fn(**kwargs: Any) -> str:
        return result

    return FunctionTool(
        name=name,
        description=f"Tool {name}",
        parameters_schema={"type": "object", "properties": {}},
        fn=fn,
    )


# ─── 基础 Agent Loop ─────────────────────────────────────────────

class TestRunnerBasic:
    """Runner.run 基础流程测试。"""

    @pytest.mark.asyncio
    async def test_simple_text_response(self) -> None:
        """最简单的路径：LLM 直接返回文本。"""
        provider = _mock_provider([_text_response("Hello!")])
        agent = Agent(name="test", instructions="Be helpful.")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "Hi", config=config)
        assert result.output == "Hello!"
        assert result.last_agent_name == "test"
        assert result.turn_count == 1
        assert result.token_usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_tool_call_then_text(self) -> None:
        """LLM 先调工具，再返回文本。"""
        tool = _make_tool("greet", "hello from tool")
        tc = ToolCall(id="tc1", name="greet", arguments="{}")
        provider = _mock_provider([
            _tool_response([tc]),
            _text_response("Final answer based on tool"),
        ])
        agent = Agent(name="test", instructions="test", tools=[tool])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "Hello", config=config)
        assert "Final answer" in result.output
        assert result.turn_count == 2

    @pytest.mark.asyncio
    async def test_max_turns_exceeded(self) -> None:
        """超过 max_turns → 返回最后一个 assistant 消息。"""
        tc = ToolCall(id="tc1", name="greet", arguments="{}")
        tool = _make_tool("greet", "ok")
        # 每轮都返回工具调用，永不停止
        provider = _mock_provider([_tool_response([tc])] * 5)
        agent = Agent(name="test", instructions="test", tools=[tool])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "Hello", config=config, max_turns=3)
        assert result.turn_count == 3


# ─── 重试逻辑 ─────────────────────────────────────────────────────

class TestRunnerRetry:
    """Runner.run LLM 重试逻辑测试。"""

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        """第一次失败，第二次成功。"""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            side_effect=[RuntimeError("API error"), _text_response("ok")],
        )
        agent = Agent(name="test", instructions="test")
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=False,
            max_retries=1,
            retry_delay=0.01,
        )

        result = await Runner.run(agent, "Hello", config=config)
        assert result.output == "ok"
        assert provider.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        """全部重试失败 → 返回错误结果（非异常）。"""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("fail"))
        agent = Agent(name="test", instructions="test")
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=False,
            max_retries=2,
            retry_delay=0.01,
        )

        result = await Runner.run(agent, "Hello", config=config)
        assert "Error" in result.output
        assert "fail" in result.output
        assert provider.chat.call_count == 3  # 1 + 2 retries


# ─── Session 集成 ─────────────────────────────────────────────────

class TestRunnerSession:
    """Runner.run Session 集成测试。"""

    @pytest.mark.asyncio
    async def test_session_load_and_save(self) -> None:
        """Session 历史加载和新消息保存。"""
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[
            Message(role=MessageRole.USER, content="old msg"),
            Message(role=MessageRole.ASSISTANT, content="old reply"),
        ])
        session.append = AsyncMock()

        provider = _mock_provider([_text_response("new reply")])
        agent = Agent(name="test", instructions="test")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "new msg", session=session, config=config)
        assert result.output == "new reply"
        session.get_history.assert_awaited_once()
        session.append.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_save_on_error(self) -> None:
        """LLM 错误时仍保存 session。"""
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])
        session.append = AsyncMock()

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("fail"))
        agent = Agent(name="test", instructions="test")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "msg", session=session, config=config)
        assert "Error" in result.output
        session.append.assert_awaited_once()


# ─── Hooks 集成 ──────────────────────────────────────────────────

class TestRunnerHooks:
    """Runner.run Hooks 调用测试。"""

    @pytest.mark.asyncio
    async def test_hooks_called_in_order(self) -> None:
        """Hooks 按正确顺序调用。"""
        events: list[str] = []

        async def on_run_start(ctx: RunContext) -> None:
            events.append("run_start")

        async def on_agent_start(ctx: RunContext, name: str) -> None:
            events.append(f"agent_start:{name}")

        async def on_llm_start(ctx: RunContext, model: str, msgs: list) -> None:
            events.append("llm_start")

        async def on_llm_end(ctx: RunContext, resp: Any) -> None:
            events.append("llm_end")

        async def on_agent_end(ctx: RunContext, name: str) -> None:
            events.append(f"agent_end:{name}")

        async def on_run_end(ctx: RunContext, result: RunResult) -> None:
            events.append("run_end")

        hooks = RunHooks(
            on_run_start=on_run_start,
            on_agent_start=on_agent_start,
            on_llm_start=on_llm_start,
            on_llm_end=on_llm_end,
            on_agent_end=on_agent_end,
            on_run_end=on_run_end,
        )
        provider = _mock_provider([_text_response("ok")])
        config = RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False)
        agent = Agent(name="test", instructions="test")

        await Runner.run(agent, "Hello", config=config)
        assert events == [
            "run_start",
            "agent_start:test",
            "llm_start",
            "llm_end",
            "agent_end:test",
            "run_end",
        ]

    @pytest.mark.asyncio
    async def test_error_hooks_on_llm_failure(self) -> None:
        """LLM 失败时 on_error 和 on_run_end 被调用。"""
        error_called = False
        run_end_called = False

        async def on_error(ctx: RunContext, err: Exception) -> None:
            nonlocal error_called
            error_called = True

        async def on_run_end(ctx: RunContext, result: RunResult) -> None:
            nonlocal run_end_called
            run_end_called = True

        hooks = RunHooks(on_error=on_error, on_run_end=on_run_end)
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("fail"))
        config = RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False)
        agent = Agent(name="test", instructions="test")

        await Runner.run(agent, "Hello", config=config)
        assert error_called
        assert run_end_called


# ─── Handoff ─────────────────────────────────────────────────────

class TestRunnerHandoff:
    """Runner.run Handoff 测试。"""

    @pytest.mark.asyncio
    async def test_handoff_switches_agent(self) -> None:
        """Handoff 切换 Agent，最终由新 Agent 返回。"""
        agent_b = Agent(name="agent_b", instructions="I am B")
        agent_a = Agent(name="agent_a", instructions="I am A", handoffs=[agent_b])

        tc = ToolCall(id="tc1", name="transfer_to_agent_b", arguments="{}")
        provider = _mock_provider([
            _tool_response([tc]),       # agent_a → handoff
            _text_response("B says hi"),  # agent_b 应答
        ])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent_a, "Hello", config=config)
        assert result.output == "B says hi"
        assert result.last_agent_name == "agent_b"


# ─── Guardrails 集成 ──────────────────────────────────────────────

class TestRunnerGuardrails:
    """Runner.run Guardrails 触发测试。"""

    @pytest.mark.asyncio
    async def test_input_guardrail_blocks(self) -> None:
        """Input guardrail 触发 → 抛 InputGuardrailTripwireError。"""
        async def block_fn(ctx: RunContext, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="blocked input")

        ig = InputGuardrail(name="blocker", guardrail_function=block_fn)
        agent = Agent(name="test", instructions="test", input_guardrails=[ig])
        # provider 不应被调用
        provider = _mock_provider([])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        with pytest.raises(InputGuardrailTripwireError, match="blocked input"):
            await Runner.run(agent, "bad input", config=config)

    @pytest.mark.asyncio
    async def test_output_guardrail_blocks(self) -> None:
        """Output guardrail 触发 → 抛 OutputGuardrailTripwireError。"""
        async def block_fn(ctx: RunContext, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="blocked output")

        og = OutputGuardrail(name="out_blocker", guardrail_function=block_fn)
        agent = Agent(name="test", instructions="test", output_guardrails=[og])
        provider = _mock_provider([_text_response("bad content")])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        with pytest.raises(OutputGuardrailTripwireError, match="blocked output"):
            await Runner.run(agent, "Hello", config=config)


# ─── Tracing 集成 ─────────────────────────────────────────────────

class TestRunnerTracing:
    """Runner.run Tracing 集成测试。"""

    @pytest.mark.asyncio
    async def test_trace_created(self) -> None:
        """tracing_enabled=True 时创建 trace。"""
        processor = AsyncMock()
        provider = _mock_provider([_text_response("ok")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[processor],
        )
        agent = Agent(name="test", instructions="test")

        result = await Runner.run(agent, "Hello", config=config)
        assert result.trace is not None
        processor.on_trace_start.assert_awaited_once()
        processor.on_trace_end.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trace_disabled(self) -> None:
        """tracing_enabled=False 时不创建 trace。"""
        provider = _mock_provider([_text_response("ok")])
        config = RunConfig(model_provider=provider, tracing_enabled=False)
        agent = Agent(name="test", instructions="test")

        result = await Runner.run(agent, "Hello", config=config)
        assert result.trace is None


# ─── Structured Output ───────────────────────────────────────────

class TestRunnerStructuredOutput:
    """Runner.run 结构化输出解析。"""

    @pytest.mark.asyncio
    async def test_pydantic_output(self) -> None:
        """output_type=Pydantic 时解析 JSON 为模型。"""
        provider = _mock_provider([_text_response('{"answer": "42"}')])
        agent = Agent(name="test", instructions="test", output_type=SampleOutput)
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "What?", config=config)
        assert isinstance(result.output, SampleOutput)
        assert result.output.answer == "42"


# ─── run_sync ─────────────────────────────────────────────────────

class TestRunSync:
    """Runner.run_sync 同步运行测试。"""

    def test_run_sync_basic(self) -> None:
        """run_sync 正常工作（无活跃事件循环场景）。"""
        provider = _mock_provider([_text_response("sync ok")])
        agent = Agent(name="test", instructions="test")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = Runner.run_sync(agent, "Hello", config=config)
        assert result.output == "sync ok"
