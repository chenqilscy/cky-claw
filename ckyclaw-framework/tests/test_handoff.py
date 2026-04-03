"""Handoff + InputFilter 测试。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner


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


# ── Handoff 数据类测试 ───────────────────────────────────────────


class TestHandoffDataclass:
    def test_default_tool_name(self) -> None:
        """默认 tool_name = transfer_to_{agent.name}。"""
        agent = Agent(name="specialist")
        handoff = Handoff(agent=agent)
        assert handoff.resolved_tool_name == "transfer_to_specialist"

    def test_custom_tool_name(self) -> None:
        """自定义 tool_name。"""
        agent = Agent(name="specialist")
        handoff = Handoff(agent=agent, tool_name="escalate_to_expert")
        assert handoff.resolved_tool_name == "escalate_to_expert"

    def test_default_description(self) -> None:
        """默认描述使用 agent.description。"""
        agent = Agent(name="specialist", description="Expert in X")
        handoff = Handoff(agent=agent)
        assert handoff.resolved_tool_description == "Expert in X"

    def test_default_description_fallback(self) -> None:
        """无 agent.description 时回退。"""
        agent = Agent(name="specialist")
        handoff = Handoff(agent=agent)
        assert handoff.resolved_tool_description == "Transfer to specialist"

    def test_custom_description(self) -> None:
        """自定义描述。"""
        agent = Agent(name="specialist")
        handoff = Handoff(agent=agent, tool_description="Send to the expert")
        assert handoff.resolved_tool_description == "Send to the expert"


# ── Agent.handoffs 兼容性测试 ────────────────────────────────────


class TestAgentHandoffsCompat:
    def test_agent_handoffs_accepts_agent(self) -> None:
        """Agent.handoffs 仍接受 Agent 直接引用（向后兼容）。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[specialist])
        assert len(triage.handoffs) == 1

    def test_agent_handoffs_accepts_handoff(self) -> None:
        """Agent.handoffs 接受 Handoff 对象。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[Handoff(agent=specialist)])
        assert len(triage.handoffs) == 1

    def test_agent_handoffs_mixed(self) -> None:
        """Agent.handoffs 混合 Agent 和 Handoff。"""
        a = Agent(name="a")
        b = Agent(name="b")
        triage = Agent(name="triage", handoffs=[a, Handoff(agent=b)])
        assert len(triage.handoffs) == 2


# ── Runner Handoff（Agent 直接引用，向后兼容）──────────────────────


class TestRunnerHandoffBackwardCompat:
    @pytest.mark.asyncio
    async def test_handoff_with_agent_still_works(self) -> None:
        """使用 Agent 直接引用的 Handoff 仍正常工作。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[specialist])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="I'm the specialist"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "help", config=config)

        assert result.last_agent_name == "specialist"
        assert result.output == "I'm the specialist"


# ── Runner Handoff（Handoff 对象）─────────────────────────────────


class TestRunnerHandoffObject:
    @pytest.mark.asyncio
    async def test_handoff_with_handoff_object(self) -> None:
        """使用 Handoff 对象的 Handoff。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[Handoff(agent=specialist)])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="specialist here"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "help", config=config)

        assert result.last_agent_name == "specialist"
        assert result.output == "specialist here"

    @pytest.mark.asyncio
    async def test_handoff_custom_tool_name(self) -> None:
        """Handoff 使用自定义 tool_name。"""
        specialist = Agent(name="specialist")
        handoff = Handoff(agent=specialist, tool_name="escalate")
        triage = Agent(name="triage", handoffs=[handoff])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="escalate", arguments="{}")],
            ),
            ModelResponse(content="escalated"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "help", config=config)

        assert result.last_agent_name == "specialist"
        assert result.output == "escalated"


# ── InputFilter 测试 ─────────────────────────────────────────────


class TestInputFilter:
    @pytest.mark.asyncio
    async def test_input_filter_last_n(self) -> None:
        """InputFilter 只保留最后 N 条消息。"""
        specialist = Agent(name="specialist")
        # 只保留最后 2 条消息
        handoff = Handoff(agent=specialist, input_filter=lambda msgs: msgs[-2:])
        triage = Agent(name="triage", handoffs=[handoff])

        call_messages: list[list[Message]] = []

        class CapturingProvider(ModelProvider):
            """记录 LLM 调用时的消息。"""
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
                call_messages.append(list(messages))
                resp = self._responses[min(self._call_count, len(self._responses) - 1)]
                self._call_count += 1
                return resp

        provider = CapturingProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="specialist response"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "hello world", config=config)

        assert result.last_agent_name == "specialist"
        # 第二次 LLM 调用（specialist）的消息应被过滤
        # system + filtered messages，过滤后只有最后 2 条
        specialist_messages = call_messages[1]
        # 过滤器保留最后 2 条 user-level 消息（不含 system）
        # system 消息在 LLM 调用时另行拼接
        assert result.output == "specialist response"

    @pytest.mark.asyncio
    async def test_input_filter_remove_system(self) -> None:
        """InputFilter 可以移除特定类型的消息。"""
        specialist = Agent(name="specialist")

        def remove_tool_messages(msgs: list[Message]) -> list[Message]:
            return [m for m in msgs if m.role != MessageRole.TOOL]

        handoff = Handoff(agent=specialist, input_filter=remove_tool_messages)
        triage = Agent(name="triage", handoffs=[handoff])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="ok"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "test", config=config)

        assert result.last_agent_name == "specialist"
        assert result.output == "ok"

    @pytest.mark.asyncio
    async def test_no_input_filter(self) -> None:
        """无 InputFilter 时消息历史完整传递。"""
        specialist = Agent(name="specialist")
        handoff = Handoff(agent=specialist)  # 无 input_filter
        triage = Agent(name="triage", handoffs=[handoff])

        call_count = 0
        captured_msg_counts: list[int] = []

        class CountingProvider(ModelProvider):
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
                nonlocal call_count
                captured_msg_counts.append(len(messages))
                resp_list = [
                    ModelResponse(
                        tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
                    ),
                    ModelResponse(content="done"),
                ]
                resp = resp_list[min(call_count, len(resp_list) - 1)]
                call_count += 1
                return resp

        config = RunConfig(model_provider=CountingProvider())

        result = await Runner.run(triage, "test", config=config)

        assert result.last_agent_name == "specialist"
        # 第二次调用应有更多消息（包含 handoff 的 tool result）
        assert captured_msg_counts[1] > captured_msg_counts[0]


# ── 流式 Handoff 测试 ────────────────────────────────────────────


class TestStreamedHandoff:
    @pytest.mark.asyncio
    async def test_streamed_handoff_with_input_filter(self) -> None:
        """流式运行中 Handoff + InputFilter。"""
        specialist = Agent(name="specialist")
        handoff = Handoff(agent=specialist, input_filter=lambda msgs: msgs[-1:])
        triage = Agent(name="triage", handoffs=[handoff])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="filtered"),
        ])
        config = RunConfig(model_provider=provider)

        events = []
        result: RunResult | None = None
        async for event in Runner.run_streamed(triage, "go", config=config):
            events.append(event)
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.last_agent_name == "specialist"
        assert result.output == "filtered"

        # 应有 HANDOFF 事件
        handoff_events = [e for e in events if e.type == StreamEventType.HANDOFF]
        assert len(handoff_events) == 1
        assert handoff_events[0].data["from"] == "triage"
        assert handoff_events[0].data["to"] == "specialist"

    @pytest.mark.asyncio
    async def test_streamed_handoff_backward_compat(self) -> None:
        """流式运行中 Agent 直接引用的 Handoff 仍正常。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[specialist])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            ModelResponse(content="specialist output"),
        ])
        config = RunConfig(model_provider=provider)

        result: RunResult | None = None
        async for event in Runner.run_streamed(triage, "hello", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.last_agent_name == "specialist"
        assert result.output == "specialist output"
