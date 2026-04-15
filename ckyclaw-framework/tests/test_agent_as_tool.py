"""Agent-as-Tool 测试。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings

# ── Mock Provider ────────────────────────────────────────────────


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


# ── Agent.as_tool() 基础测试 ─────────────────────────────────────


class TestAsToolBasic:
    def test_returns_function_tool(self) -> None:
        """as_tool() 返回 FunctionTool 实例。"""
        agent = Agent(name="helper", description="A helpful agent")
        tool = agent.as_tool()
        assert isinstance(tool, FunctionTool)
        assert tool.name == "helper"
        assert tool.description == "A helpful agent"

    def test_custom_name_and_description(self) -> None:
        """as_tool 支持自定义名称和描述。"""
        agent = Agent(name="helper")
        tool = agent.as_tool(tool_name="my_helper", tool_description="Custom desc")
        assert tool.name == "my_helper"
        assert tool.description == "Custom desc"

    def test_default_description_fallback(self) -> None:
        """无 description 时使用默认回退。"""
        agent = Agent(name="helper")
        tool = agent.as_tool()
        assert tool.description == "Run agent 'helper'"

    def test_parameters_schema(self) -> None:
        """参数 schema 应包含 input 字段。"""
        agent = Agent(name="helper")
        tool = agent.as_tool()
        schema = tool.parameters_schema
        assert "properties" in schema
        assert "input" in schema["properties"]
        assert schema["properties"]["input"]["type"] == "string"
        assert schema["required"] == ["input"]

    def test_to_openai_schema(self) -> None:
        """生成的 FunctionTool 应能转为 OpenAI schema。"""
        agent = Agent(name="helper", description="Helpful")
        tool = agent.as_tool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "helper"
        assert schema["function"]["description"] == "Helpful"


# ── Agent-as-Tool 执行测试 ───────────────────────────────────────


class TestAsToolExecution:
    @pytest.mark.asyncio
    async def test_agent_tool_executes(self) -> None:
        """Agent-as-Tool 应能执行并返回子 Agent 输出。"""
        # 子 Agent 的 provider
        sub_provider = MockProvider([
            ModelResponse(content="Sub agent result"),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        sub_agent = Agent(name="sub-agent", instructions="You are a sub agent.")
        tool = sub_agent.as_tool(config=sub_config)

        result = await tool.execute({"input": "Hello sub agent"})

        assert result == "Sub agent result"

    @pytest.mark.asyncio
    async def test_manager_calls_agent_tool(self) -> None:
        """Manager Agent 通过 tool_call 调用 Agent-as-Tool。"""
        # 子 Agent provider: 直接返回文本
        sub_provider = MockProvider([
            ModelResponse(content="Data analysis complete: revenue is $1M"),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        # 子 Agent
        analyst = Agent(name="analyst", description="Data analyst agent")
        analyst_tool = analyst.as_tool(config=sub_config)

        # Manager Agent provider: 先调用 analyst tool，再根据结果回复
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="analyst",
                    arguments=json.dumps({"input": "Analyze Q1 revenue"}),
                )],
            ),
            ModelResponse(content="Based on analysis: revenue is $1M"),
        ])
        manager_config = RunConfig(model_provider=manager_provider)

        manager = Agent(
            name="manager",
            instructions="You are a manager.",
            tools=[analyst_tool],
        )

        result = await Runner.run(manager, "What's Q1 revenue?", config=manager_config)

        assert result.output == "Based on analysis: revenue is $1M"
        assert result.last_agent_name == "manager"
        assert result.turn_count == 2  # 第一轮 tool_call，第二轮最终回复

    @pytest.mark.asyncio
    async def test_agent_tool_independent_history(self) -> None:
        """Agent-as-Tool 使用独立消息历史，不共享 Manager 对话。"""
        captured_messages: list[list[Message]] = []

        class CapturingProvider(ModelProvider):
            """记录每次 LLM 调用的消息。"""
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
                captured_messages.append(list(messages))
                resp = self._responses[min(self._call_count, len(self._responses) - 1)]
                self._call_count += 1
                return resp

        # 子 Agent 的 provider
        sub_provider = CapturingProvider([
            ModelResponse(content="42"),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        sub_agent = Agent(name="calculator", instructions="You calculate things.")
        calc_tool = sub_agent.as_tool(config=sub_config)

        # Manager 有复杂的历史
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="calculator",
                    arguments=json.dumps({"input": "What is 6*7?"}),
                )],
            ),
            ModelResponse(content="The answer is 42"),
        ])
        manager_config = RunConfig(model_provider=manager_provider)

        manager = Agent(name="manager", tools=[calc_tool])

        result = await Runner.run(manager, "Calculate 6*7", config=manager_config)

        assert result.output == "The answer is 42"
        # 子 Agent 的 LLM 调用只应收到: system(if any) + user("What is 6*7?")
        sub_messages = captured_messages[0]
        user_messages = [m for m in sub_messages if m.role == MessageRole.USER]
        assert len(user_messages) == 1
        assert user_messages[0].content == "What is 6*7?"


# ── Agent-as-Tool 流式测试 ───────────────────────────────────────


class TestAsToolStreamed:
    @pytest.mark.asyncio
    async def test_streamed_with_agent_tool(self) -> None:
        """流式运行中 Agent-as-Tool 也能正常工作。"""
        sub_provider = MockProvider([
            ModelResponse(content="Sub result"),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        sub_agent = Agent(name="sub")
        sub_tool = sub_agent.as_tool(config=sub_config)

        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="sub",
                    arguments=json.dumps({"input": "do something"}),
                )],
            ),
            ModelResponse(content="Done via sub"),
        ])
        manager_config = RunConfig(model_provider=manager_provider)

        manager = Agent(name="manager", tools=[sub_tool])

        result: RunResult | None = None
        async for event in Runner.run_streamed(manager, "go", config=manager_config):
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.output == "Done via sub"
        assert result.last_agent_name == "manager"


# ── 边界条件 ─────────────────────────────────────────────────────


class TestAsToolEdgeCases:
    @pytest.mark.asyncio
    async def test_agent_tool_sub_agent_error(self) -> None:
        """子 Agent LLM 失败时，tool_result 应包含错误信息。"""
        class FailingProvider(ModelProvider):
            async def chat(self, model: str, messages: list[Message], **kwargs: Any) -> ModelResponse:
                raise RuntimeError("LLM is down")

        sub_config = RunConfig(model_provider=FailingProvider())
        sub_agent = Agent(name="failing-agent")
        fail_tool = sub_agent.as_tool(config=sub_config)

        # 直接执行 tool
        result = await fail_tool.execute({"input": "test"})

        # FunctionTool.execute 捕获异常返回 error string
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_multiple_agent_tools(self) -> None:
        """Manager 同时拥有多个 Agent-as-Tool。"""
        agent_a = Agent(name="agent-a")
        agent_b = Agent(name="agent-b")

        provider_a = MockProvider([ModelResponse(content="A result")])
        provider_b = MockProvider([ModelResponse(content="B result")])

        tool_a = agent_a.as_tool(config=RunConfig(model_provider=provider_a))
        tool_b = agent_b.as_tool(config=RunConfig(model_provider=provider_b))

        # Manager 调用 agent-a
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="agent-a",
                    arguments=json.dumps({"input": "query A"}),
                )],
            ),
            ModelResponse(content="Got A result"),
        ])
        manager_config = RunConfig(model_provider=manager_provider)

        manager = Agent(name="manager", tools=[tool_a, tool_b])
        result = await Runner.run(manager, "ask A", config=manager_config)

        assert result.output == "Got A result"
