"""Runner Agent Loop 单元测试。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import function_tool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings

# ── Mock Model Provider ─────────────────────────────────────────


class MockProvider(ModelProvider):
    """可编排的 Mock LLM 提供商。按顺序返回预设响应。"""

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
        # 将 ModelResponse 拆为多个 chunk 模拟流式
        if resp.content:
            words = resp.content.split(" ")
            for i, w in enumerate(words):
                suffix = " " if i < len(words) - 1 else ""
                yield ModelChunk(content=w + suffix)
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield ModelChunk(
                    tool_call_chunks=[
                        ToolCallChunk(index=i, id=tc.id, name=tc.name, arguments_delta=tc.arguments),
                    ],
                )
        yield ModelChunk(finish_reason="stop")


# ── 基本执行测试 ─────────────────────────────────────────────


class TestRunnerBasic:
    @pytest.mark.asyncio
    async def test_simple_chat(self) -> None:
        """纯文本对话——无工具调用。"""
        agent = Agent(name="echo", instructions="You are a helpful assistant.")
        provider = MockProvider([
            ModelResponse(content="Hello, world!", token_usage=TokenUsage(10, 5, 15)),
        ])

        result = await Runner.run(
            agent,
            "Hi!",
            config=RunConfig(model_provider=provider),
        )

        assert result.output == "Hello, world!"
        assert result.last_agent_name == "echo"
        assert result.turn_count == 1
        assert result.token_usage is not None
        assert result.token_usage.total_tokens == 15
        assert len(result.messages) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_string_input(self) -> None:
        """字符串输入自动转换为 Message。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="OK")])

        result = await Runner.run(agent, "test", config=RunConfig(model_provider=provider))

        assert result.messages[0].role == MessageRole.USER
        assert result.messages[0].content == "test"

    @pytest.mark.asyncio
    async def test_message_list_input(self) -> None:
        """支持直接传入 Message 列表。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="noted")])

        messages = [
            Message(role=MessageRole.USER, content="message 1"),
            Message(role=MessageRole.USER, content="message 2"),
        ]
        result = await Runner.run(agent, messages, config=RunConfig(model_provider=provider))

        assert result.output == "noted"
        assert result.messages[0].content == "message 1"

    @pytest.mark.asyncio
    async def test_dynamic_instructions(self) -> None:
        """动态 instructions 函数被正确调用。"""
        def dynamic_instructions(ctx: Any) -> str:
            return f"You are agent {ctx.agent.name}, turn {ctx.turn_count}"

        agent = Agent(name="dynamic", instructions=dynamic_instructions)
        provider = MockProvider([ModelResponse(content="ok")])

        result = await Runner.run(agent, "hi", config=RunConfig(model_provider=provider))
        assert result.output == "ok"


# ── 工具调用测试 ─────────────────────────────────────────────


class TestRunnerToolCalls:
    @pytest.mark.asyncio
    async def test_single_tool_call(self) -> None:
        """单次工具调用 → LLM 用结果生成最终回复。"""
        @function_tool()
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        agent = Agent(name="calc", tools=[add])
        provider = MockProvider([
            # 第 1 轮：LLM 请求调用 add 工具
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="add", arguments='{"a": 3, "b": 5}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # 第 2 轮：LLM 看到工具结果后给出最终回复
            ModelResponse(
                content="The sum is 8.",
                token_usage=TokenUsage(20, 10, 30),
            ),
        ])

        result = await Runner.run(agent, "What is 3 + 5?", config=RunConfig(model_provider=provider))

        assert result.output == "The sum is 8."
        assert result.turn_count == 2
        assert result.token_usage is not None
        assert result.token_usage.total_tokens == 45  # 15 + 30

        # 检查消息历史：user → assistant(tool_call) → tool(result) → assistant(final)
        assert len(result.messages) == 4
        assert result.messages[0].role == MessageRole.USER
        assert result.messages[1].role == MessageRole.ASSISTANT
        assert result.messages[1].tool_calls is not None
        assert result.messages[2].role == MessageRole.TOOL
        assert result.messages[2].content == "8"
        assert result.messages[3].role == MessageRole.ASSISTANT
        assert result.messages[3].content == "The sum is 8."

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self) -> None:
        """多次工具调用循环。"""
        @function_tool()
        def multiply(a: int, b: int) -> int:
            """Multiply."""
            return a * b

        @function_tool()
        def format_number(n: int) -> str:
            """Format."""
            return f"Result: {n}"

        agent = Agent(name="calc", tools=[multiply, format_number])
        provider = MockProvider([
            # 第 1 轮：调用 multiply
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="multiply", arguments='{"a": 4, "b": 5}')],
            ),
            # 第 2 轮：调用 format_number
            ModelResponse(
                tool_calls=[ToolCall(id="c2", name="format_number", arguments='{"n": 20}')],
            ),
            # 第 3 轮：最终回复
            ModelResponse(content="4 times 5 is Result: 20"),
        ])

        result = await Runner.run(agent, "4 * 5", config=RunConfig(model_provider=provider))

        assert result.output == "4 times 5 is Result: 20"
        assert result.turn_count == 3

    @pytest.mark.asyncio
    async def test_tool_not_found(self) -> None:
        """LLM 请求不存在的工具 → 返回错误消息。"""
        agent = Agent(name="bot", tools=[])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="nonexistent", arguments="{}")],
            ),
            ModelResponse(content="Sorry, something went wrong."),
        ])

        result = await Runner.run(agent, "test", config=RunConfig(model_provider=provider))
        # 工具错误消息应在历史中
        tool_msg = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msg) == 1
        assert "not found" in tool_msg[0].content.lower()

    @pytest.mark.asyncio
    async def test_tool_execution_error(self) -> None:
        """工具执行抛异常 → 错误结果返回给 LLM。"""
        @function_tool()
        def boom() -> str:
            """Goes boom."""
            raise ValueError("kaboom!")

        agent = Agent(name="bot", tools=[boom])
        provider = MockProvider([
            ModelResponse(tool_calls=[ToolCall(id="c1", name="boom", arguments="{}")]),
            ModelResponse(content="There was an error."),
        ])

        result = await Runner.run(agent, "test", config=RunConfig(model_provider=provider))
        tool_msg = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert "kaboom" in tool_msg[0].content


# ── Handoff 测试 ─────────────────────────────────────────────


class TestRunnerHandoff:
    @pytest.mark.asyncio
    async def test_handoff_to_target_agent(self) -> None:
        """Handoff: Agent A 将控制权转移给 Agent B。"""
        agent_b = Agent(name="specialist", instructions="You are a specialist.")
        agent_a = Agent(name="triage", instructions="You are a triage agent.", handoffs=[agent_b])

        provider = MockProvider([
            # Agent A 请求 Handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            # Agent B 执行回复
            ModelResponse(content="I'm the specialist. How can I help?"),
        ])

        result = await Runner.run(agent_a, "I need a specialist", config=RunConfig(model_provider=provider))

        assert result.output == "I'm the specialist. How can I help?"
        assert result.last_agent_name == "specialist"
        # Handoff 不计为额外 turn
        assert result.turn_count == 1

    @pytest.mark.asyncio
    async def test_handoff_preserves_history(self) -> None:
        """Handoff 后消息历史完整保留。"""
        agent_b = Agent(name="b")
        agent_a = Agent(name="a", handoffs=[agent_b])

        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_b", arguments="{}")],
            ),
            ModelResponse(content="Done by B"),
        ])

        result = await Runner.run(agent_a, "start", config=RunConfig(model_provider=provider))

        # 消息应包含：user → assistant(handoff tool_call) → tool(empty) → assistant(B reply)
        roles = [m.role for m in result.messages]
        assert roles == [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.TOOL, MessageRole.ASSISTANT]


# ── max_turns 测试 ───────────────────────────────────────────


class TestRunnerMaxTurns:
    @pytest.mark.asyncio
    async def test_max_turns_exceeded(self) -> None:
        """超过 max_turns 时正常返回最后一条输出。"""
        @function_tool()
        def noop() -> str:
            """Do nothing."""
            return "ok"

        agent = Agent(name="loop", tools=[noop])
        # LLM 始终请求工具调用，永不给出最终回复
        infinite_tool_call = ModelResponse(
            tool_calls=[ToolCall(id="c", name="noop", arguments="{}")],
        )
        provider = MockProvider([infinite_tool_call] * 20)

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider), max_turns=3)

        assert result.turn_count == 3


# ── run_sync 测试 ────────────────────────────────────────────


class TestRunnerSync:
    def test_run_sync(self) -> None:
        """同步接口正常工作。"""
        agent = Agent(name="sync-bot")
        provider = MockProvider([ModelResponse(content="sync reply")])

        result = Runner.run_sync(agent, "hi", config=RunConfig(model_provider=provider))
        assert result.output == "sync reply"


# ── 流式执行测试 ─────────────────────────────────────────────


class TestRunnerStreamed:
    @pytest.mark.asyncio
    async def test_stream_basic(self) -> None:
        """流式模式正常产出事件序列。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Hello world")])

        events = []
        async for event in Runner.run_streamed(
            agent, "Hi", config=RunConfig(model_provider=provider),
        ):
            events.append(event)

        event_types = [e.type for e in events]
        assert StreamEventType.AGENT_START in event_types
        assert StreamEventType.LLM_CHUNK in event_types
        assert StreamEventType.RUN_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self) -> None:
        """流式模式下工具调用事件正确产出。"""
        @function_tool()
        def calc(a: int) -> int:
            """Calc."""
            return a * 2

        agent = Agent(name="bot", tools=[calc])
        provider = MockProvider([
            ModelResponse(tool_calls=[ToolCall(id="c1", name="calc", arguments='{"a": 5}')]),
            ModelResponse(content="Result is 10"),
        ])

        events = []
        async for event in Runner.run_streamed(
            agent, "double 5", config=RunConfig(model_provider=provider),
        ):
            events.append(event)

        event_types = [e.type for e in events]
        assert StreamEventType.TOOL_CALL_START in event_types
        assert StreamEventType.TOOL_CALL_END in event_types
        assert StreamEventType.RUN_COMPLETE in event_types

        # 提取最终结果
        complete_event = [e for e in events if e.type == StreamEventType.RUN_COMPLETE][0]
        assert isinstance(complete_event.data, RunResult)
        assert complete_event.data.output == "Result is 10"

    @pytest.mark.asyncio
    async def test_stream_handoff(self) -> None:
        """流式模式下 Handoff 事件正确产出。"""
        agent_b = Agent(name="b")
        agent_a = Agent(name="a", handoffs=[agent_b])

        provider = MockProvider([
            ModelResponse(tool_calls=[ToolCall(id="h1", name="transfer_to_b", arguments="{}")]),
            ModelResponse(content="Response from B"),
        ])

        events = []
        async for event in Runner.run_streamed(
            agent_a, "need b", config=RunConfig(model_provider=provider),
        ):
            events.append(event)

        event_types = [e.type for e in events]
        assert StreamEventType.HANDOFF in event_types
        handoff_event = [e for e in events if e.type == StreamEventType.HANDOFF][0]
        assert handoff_event.data["from"] == "a"
        assert handoff_event.data["to"] == "b"


# ── 模型/配置解析测试 ────────────────────────────────────────


class TestRunnerErrorHandling:
    @pytest.mark.asyncio
    async def test_llm_call_failure(self) -> None:
        """LLM 调用异常被捕获并返回错误结果。"""
        agent = Agent(name="bot")

        class FailProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                raise ConnectionError("Network down")

        result = await Runner.run(agent, "hi", config=RunConfig(model_provider=FailProvider()))
        assert "Error" in result.output
        assert "Network down" in result.output

    @pytest.mark.asyncio
    async def test_empty_instructions_no_empty_system_msg(self) -> None:
        """空 instructions 不发送空 system message。"""
        agent = Agent(name="bot", instructions="")

        call_args: dict[str, Any] = {}

        class SpyProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                call_args["messages"] = messages
                return ModelResponse(content="ok")

        await Runner.run(agent, "hi", config=RunConfig(model_provider=SpyProvider()))
        # 不应有 system 消息
        roles = [m.role for m in call_args["messages"]]
        assert MessageRole.SYSTEM not in roles


class TestRunnerConfigResolution:
    @pytest.mark.asyncio
    async def test_config_model_override(self) -> None:
        """RunConfig.model 优先于 Agent.model。"""
        agent = Agent(name="bot", model="gpt-3.5-turbo")

        call_args: dict[str, Any] = {}

        class SpyProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                call_args["model"] = model
                return ModelResponse(content="ok")

        await Runner.run(
            agent, "hi",
            config=RunConfig(model="gpt-4o", model_provider=SpyProvider()),
        )
        assert call_args["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_agent_model_fallback(self) -> None:
        """无 RunConfig.model 时使用 Agent.model。"""
        agent = Agent(name="bot", model="claude-3-haiku")

        call_args: dict[str, Any] = {}

        class SpyProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                call_args["model"] = model
                return ModelResponse(content="ok")

        await Runner.run(
            agent, "hi",
            config=RunConfig(model_provider=SpyProvider()),
        )
        assert call_args["model"] == "claude-3-haiku"

    @pytest.mark.asyncio
    async def test_default_model_fallback(self) -> None:
        """Agent 和 RunConfig 都未指定模型时使用默认值。"""
        agent = Agent(name="bot")

        call_args: dict[str, Any] = {}

        class SpyProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                call_args["model"] = model
                return ModelResponse(content="ok")

        await Runner.run(
            agent, "hi",
            config=RunConfig(model_provider=SpyProvider()),
        )
        assert call_args["model"] == "gpt-4o-mini"


# ── 并行工具执行 & 超时测试 ──────────────────────────────────


class TestParallelToolExecution:
    """验证多工具调用并行执行和 RunConfig.tool_timeout。"""

    @pytest.mark.asyncio
    async def test_multiple_tools_execute_in_parallel(self) -> None:
        """多个工具应并行执行——总耗时应远小于串行之和。"""
        import time

        @function_tool()
        async def slow_a() -> str:
            """Slow A."""
            await asyncio.sleep(0.2)
            return "A done"

        @function_tool()
        async def slow_b() -> str:
            """Slow B."""
            await asyncio.sleep(0.2)
            return "B done"

        agent = Agent(name="bot", tools=[slow_a, slow_b])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="slow_a", arguments="{}"),
                    ToolCall(id="c2", name="slow_b", arguments="{}"),
                ],
            ),
            ModelResponse(content="Both done."),
        ])

        start = time.monotonic()
        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        elapsed = time.monotonic() - start

        assert result.output == "Both done."
        # 并行：0.2s 左右；串行需 0.4s+
        assert elapsed < 0.35, f"Expected parallel execution, but took {elapsed:.2f}s"

        # 两个 tool 结果都在消息中
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 2

    @pytest.mark.asyncio
    async def test_single_tool_no_taskgroup_overhead(self) -> None:
        """单个工具调用不使用 TaskGroup，直接执行。"""
        @function_tool()
        def echo(text: str) -> str:
            """Echo."""
            return text

        agent = Agent(name="bot", tools=[echo])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments='{"text": "hello"}')],
            ),
            ModelResponse(content="echo: hello"),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        assert result.output == "echo: hello"

    @pytest.mark.asyncio
    async def test_parallel_with_one_error(self) -> None:
        """并行执行中一个工具异常不影响其他工具。"""
        @function_tool()
        async def good_tool() -> str:
            """Good."""
            await asyncio.sleep(0.05)
            return "ok"

        @function_tool()
        async def bad_tool() -> str:
            """Bad."""
            raise ValueError("boom")

        agent = Agent(name="bot", tools=[good_tool, bad_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="good_tool", arguments="{}"),
                    ToolCall(id="c2", name="bad_tool", arguments="{}"),
                ],
            ),
            ModelResponse(content="Done with errors."),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 2
        # good_tool 成功
        good = next(m for m in tool_msgs if "ok" in m.content)
        assert good is not None
        # bad_tool 错误
        bad = next(m for m in tool_msgs if "boom" in m.content)
        assert bad is not None

    @pytest.mark.asyncio
    async def test_parallel_preserves_message_order(self) -> None:
        """并行执行后结果按原始 tool_call 顺序追加到 messages。"""
        @function_tool()
        async def tool_first() -> str:
            """First."""
            await asyncio.sleep(0.15)  # 第一个完成更慢
            return "FIRST"

        @function_tool()
        async def tool_second() -> str:
            """Second."""
            await asyncio.sleep(0.05)  # 第二个完成更快
            return "SECOND"

        agent = Agent(name="bot", tools=[tool_first, tool_second])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="tool_first", arguments="{}"),
                    ToolCall(id="c2", name="tool_second", arguments="{}"),
                ],
            ),
            ModelResponse(content="ordered"),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 2
        # 即使 tool_second 先完成，消息顺序仍是 first → second
        assert tool_msgs[0].content == "FIRST"
        assert tool_msgs[1].content == "SECOND"

    @pytest.mark.asyncio
    async def test_handoff_with_parallel_tools(self) -> None:
        """Handoff 之前的普通工具并行执行，然后 Handoff 控制权转移。"""
        @function_tool()
        async def prepare() -> str:
            """Prepare."""
            return "prepared"

        specialist = Agent(name="specialist")
        agent = Agent(name="triage", tools=[prepare], handoffs=[specialist])

        provider = MockProvider([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="prepare", arguments="{}"),
                    ToolCall(id="c2", name="transfer_to_specialist", arguments="{}"),
                ],
            ),
            # specialist 执行回复
            ModelResponse(content="Specialist here."),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        assert result.output == "Specialist here."
        # prepare 工具结果和 handoff 空结果都在消息中
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 2
        assert tool_msgs[0].content == "prepared"
        assert tool_msgs[1].content == ""  # Handoff 空结果


class TestToolTimeout:
    """工具超时相关测试。"""

    @pytest.mark.asyncio
    async def test_tool_level_timeout(self) -> None:
        """FunctionTool.timeout 优先，超时返回错误。"""
        @function_tool(timeout=0.1)
        async def slow_tool() -> str:
            """Slow."""
            await asyncio.sleep(5)
            return "never"

        agent = Agent(name="bot", tools=[slow_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="slow_tool", arguments="{}")],
            ),
            ModelResponse(content="timed out"),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert "timed out" in tool_msgs[0].content.lower()

    @pytest.mark.asyncio
    async def test_config_tool_timeout_fallback(self) -> None:
        """RunConfig.tool_timeout 作为全局回退：当工具无自身 timeout 时生效。"""
        @function_tool()
        async def slow_tool() -> str:
            """Slow."""
            await asyncio.sleep(5)
            return "never"

        agent = Agent(name="bot", tools=[slow_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="slow_tool", arguments="{}")],
            ),
            ModelResponse(content="caught timeout"),
        ])

        result = await Runner.run(
            agent, "go",
            config=RunConfig(model_provider=provider, tool_timeout=0.1),
        )
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert "timed out" in tool_msgs[0].content.lower()

    @pytest.mark.asyncio
    async def test_tool_timeout_priority_over_config(self) -> None:
        """FunctionTool.timeout 优先于 RunConfig.tool_timeout。"""

        # 工具有 5s 超时，RunConfig 有 0.05s — 工具有自身 timeout，用自身的
        @function_tool(timeout=5.0)
        async def fast_tool() -> str:
            """Fast with long timeout."""
            return "fast"

        agent = Agent(name="bot", tools=[fast_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="fast_tool", arguments="{}")],
            ),
            ModelResponse(content="ok"),
        ])

        result = await Runner.run(
            agent, "go",
            config=RunConfig(model_provider=provider, tool_timeout=0.05),
        )
        # 工具使用自身 timeout=5s，不会超时
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert tool_msgs[0].content == "fast"

    @pytest.mark.asyncio
    async def test_no_timeout_by_default(self) -> None:
        """默认无超时——工具正常执行。"""
        @function_tool()
        async def normal_tool() -> str:
            """Normal."""
            await asyncio.sleep(0.05)
            return "done"

        agent = Agent(name="bot", tools=[normal_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="normal_tool", arguments="{}")],
            ),
            ModelResponse(content="ok"),
        ])

        result = await Runner.run(agent, "go", config=RunConfig(model_provider=provider))
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert tool_msgs[0].content == "done"
