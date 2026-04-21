"""Runner Lifecycle Hooks 单元测试。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from kasaya.agent.agent import Agent
from kasaya.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from kasaya.runner.hooks import RunHooks, _invoke_hook
from kasaya.runner.run_config import RunConfig
from kasaya.runner.runner import Runner
from kasaya.tools.function_tool import function_tool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from kasaya.model.message import Message
    from kasaya.model.settings import ModelSettings
    from kasaya.runner.run_context import RunContext

# ── Mock Model Provider ─────────────────────────────────────────


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
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield ModelChunk(
                    tool_call_chunks=[
                        ToolCallChunk(index=i, id=tc.id, name=tc.name, arguments_delta=tc.arguments),
                    ],
                )
        yield ModelChunk(finish_reason="stop")


class FailingProvider(ModelProvider):
    """始终抛异常的 Provider。"""

    async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
        raise RuntimeError("LLM exploded")


# ── Helper ───────────────────────────────────────────────────


def _make_hooks() -> tuple[RunHooks, list[str]]:
    """创建 RunHooks 实例，所有 hook 记录调用顺序到共享列表。"""
    log: list[str] = []

    async def on_run_start(ctx: RunContext) -> None:
        log.append("run_start")

    async def on_run_end(ctx: RunContext, result_or_error: Any) -> None:
        log.append("run_end")

    async def on_agent_start(ctx: RunContext, agent_name: str) -> None:
        log.append(f"agent_start:{agent_name}")

    async def on_agent_end(ctx: RunContext, agent_name: str) -> None:
        log.append(f"agent_end:{agent_name}")

    async def on_llm_start(ctx: RunContext, model: str, messages: list[Any]) -> None:
        log.append(f"llm_start:{model}")

    async def on_llm_end(ctx: RunContext, response: ModelResponse) -> None:
        log.append("llm_end")

    async def on_tool_start(ctx: RunContext, tool_name: str, arguments: dict) -> None:
        log.append(f"tool_start:{tool_name}")

    async def on_tool_end(ctx: RunContext, tool_name: str, result: str) -> None:
        log.append(f"tool_end:{tool_name}")

    async def on_handoff(ctx: RunContext, from_agent: str, to_agent: str) -> None:
        log.append(f"handoff:{from_agent}->{to_agent}")

    async def on_error(ctx: RunContext, error: Exception) -> None:
        log.append(f"error:{type(error).__name__}")

    hooks = RunHooks(
        on_run_start=on_run_start,
        on_run_end=on_run_end,
        on_agent_start=on_agent_start,
        on_agent_end=on_agent_end,
        on_llm_start=on_llm_start,
        on_llm_end=on_llm_end,
        on_tool_start=on_tool_start,
        on_tool_end=on_tool_end,
        on_handoff=on_handoff,
        on_error=on_error,
    )
    return hooks, log


# ── Tests ────────────────────────────────────────────────────


class TestInvokeHook:
    """_invoke_hook 基础行为。"""

    @pytest.mark.asyncio
    async def test_none_hook_is_noop(self) -> None:
        await _invoke_hook(None, "test")  # 不应抛异常

    @pytest.mark.asyncio
    async def test_exception_is_swallowed(self) -> None:
        async def boom() -> None:
            raise ValueError("kaboom")

        # 异常被吞掉，不影响调用方
        await _invoke_hook(boom, "boom_hook")

    @pytest.mark.asyncio
    async def test_normal_hook_called(self) -> None:
        called = False

        async def my_hook(x: int) -> None:
            nonlocal called
            called = True
            assert x == 42

        await _invoke_hook(my_hook, "my_hook", 42)
        assert called


class TestRunHooksSimpleChat:
    """纯文本对话——验证 run_start/agent_start/llm_start/llm_end/agent_end/run_end 顺序。"""

    @pytest.mark.asyncio
    async def test_hook_order_run(self) -> None:
        hooks, log = _make_hooks()
        agent = Agent(name="bot", instructions="Hi")
        provider = MockProvider([ModelResponse(content="OK")])

        result = await Runner.run(
            agent, "Hello",
            config=RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False),
        )
        assert result.output == "OK"
        assert log == [
            "run_start",
            "agent_start:bot",
            "llm_start:gpt-4o-mini",
            "llm_end",
            "agent_end:bot",
            "run_end",
        ]

    @pytest.mark.asyncio
    async def test_hook_order_run_streamed(self) -> None:
        hooks, log = _make_hooks()
        agent = Agent(name="bot", instructions="Hi")
        provider = MockProvider([ModelResponse(content="OK")])

        events = []
        async for event in Runner.run_streamed(
            agent, "Hello",
            config=RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False),
        ):
            events.append(event.type)

        assert log == [
            "run_start",
            "agent_start:bot",
            "llm_start:gpt-4o-mini",
            "llm_end",
            "agent_end:bot",
            "run_end",
        ]


class TestRunHooksWithTools:
    """带工具调用——验证 tool_start/tool_end 触发。"""

    @pytest.mark.asyncio
    async def test_tool_hooks_fire(self) -> None:
        hooks, log = _make_hooks()

        @function_tool()
        async def add(a: int, b: int) -> str:
            """Add two numbers."""
            return str(a + b)

        agent = Agent(name="math", instructions="...", tools=[add])
        provider = MockProvider([
            ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="add", arguments=json.dumps({"a": 1, "b": 2}))],
            ),
            ModelResponse(content="3"),
        ])

        result = await Runner.run(
            agent, "1+2",
            config=RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False),
        )
        assert result.output == "3"
        assert "tool_start:add" in log
        assert "tool_end:add" in log
        # tool_start 在 tool_end 之前
        assert log.index("tool_start:add") < log.index("tool_end:add")


class TestRunHooksWithHandoff:
    """Handoff——验证 on_handoff + 正确的 agent_end/agent_start。"""

    @pytest.mark.asyncio
    async def test_handoff_hooks(self) -> None:
        hooks, log = _make_hooks()

        target = Agent(name="specialist", instructions="I handle special tasks.")
        agent = Agent(name="router", instructions="Route.", handoffs=[target])

        provider = MockProvider([
            # 第一轮: router 产出 handoff 工具调用
            ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            # 第二轮: specialist 产出最终回复
            ModelResponse(content="Done by specialist"),
        ])

        result = await Runner.run(
            agent, "Handle this",
            config=RunConfig(model_provider=provider, hooks=hooks, tracing_enabled=False),
        )
        assert result.output == "Done by specialist"
        assert "handoff:router->specialist" in log
        assert "agent_end:router" in log
        assert "agent_start:specialist" in log


class TestRunHooksOnError:
    """LLM 调用失败——验证 on_error + on_run_end 触发。"""

    @pytest.mark.asyncio
    async def test_error_hook_run(self) -> None:
        hooks, log = _make_hooks()
        agent = Agent(name="fail", instructions="oops")

        result = await Runner.run(
            agent, "go",
            config=RunConfig(model_provider=FailingProvider(), hooks=hooks, tracing_enabled=False),
        )
        assert "Error" in result.output
        assert "error:RuntimeError" in log
        assert "run_end" in log

    @pytest.mark.asyncio
    async def test_error_hook_run_streamed(self) -> None:
        hooks, log = _make_hooks()
        agent = Agent(name="fail", instructions="oops")

        events = []
        async for event in Runner.run_streamed(
            agent, "go",
            config=RunConfig(model_provider=FailingProvider(), hooks=hooks, tracing_enabled=False),
        ):
            events.append(event)

        assert "error:RuntimeError" in log
        assert "run_end" in log


class TestHookExceptionNonBlocking:
    """Hook 抛异常不影响 Agent 执行。"""

    @pytest.mark.asyncio
    async def test_hook_exception_does_not_break_run(self) -> None:
        async def exploding_hook(*args: Any) -> None:
            raise ValueError("hook exploded")

        broken_hooks = RunHooks(
            on_run_start=exploding_hook,
            on_agent_start=exploding_hook,
            on_llm_start=exploding_hook,
            on_llm_end=exploding_hook,
            on_agent_end=exploding_hook,
            on_run_end=exploding_hook,
        )
        agent = Agent(name="sturdy", instructions="You are sturdy.")
        provider = MockProvider([ModelResponse(content="Still works!")])

        result = await Runner.run(
            agent, "test",
            config=RunConfig(model_provider=provider, hooks=broken_hooks, tracing_enabled=False),
        )
        assert result.output == "Still works!"


class TestNoHooksIsNoop:
    """不配置 hooks 时不影响执行。"""

    @pytest.mark.asyncio
    async def test_no_hooks(self) -> None:
        agent = Agent(name="plain", instructions="Hi")
        provider = MockProvider([ModelResponse(content="OK")])

        result = await Runner.run(
            agent, "hi",
            config=RunConfig(model_provider=provider, tracing_enabled=False),
        )
        assert result.output == "OK"
