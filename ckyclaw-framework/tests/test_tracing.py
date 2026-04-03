"""Tracing 自动采集测试。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import function_tool
from ckyclaw_framework.tracing.console_processor import ConsoleTraceProcessor
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace


# ── 收集型 TraceProcessor ────────────────────────────────────────


class CollectorProcessor(TraceProcessor):
    """收集所有 Trace/Span 事件用于断言。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def on_trace_start(self, trace: Trace) -> None:
        self.events.append(("trace_start", trace))

    async def on_span_start(self, span: Span) -> None:
        self.events.append(("span_start", span))

    async def on_span_end(self, span: Span) -> None:
        self.events.append(("span_end", span))

    async def on_trace_end(self, trace: Trace) -> None:
        self.events.append(("trace_end", trace))


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
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield ModelChunk(
                    tool_call_chunks=[
                        ToolCallChunk(index=i, id=tc.id, name=tc.name, arguments_delta=tc.arguments),
                    ],
                )
        yield ModelChunk(finish_reason="stop")


# ── 基础 Span/Trace 测试 ─────────────────────────────────────────


class TestSpanTrace:
    def test_span_defaults(self) -> None:
        """Span 应有默认 span_id 和 start_time。"""
        span = Span(trace_id="t1", type=SpanType.AGENT, name="test")
        assert span.span_id
        assert span.start_time is not None
        assert span.status == SpanStatus.PENDING

    def test_trace_defaults(self) -> None:
        """Trace 应有默认 trace_id 和 start_time。"""
        trace = Trace(workflow_name="test")
        assert trace.trace_id
        assert trace.start_time is not None
        assert trace.spans == []

    def test_span_type_values(self) -> None:
        """SpanType 枚举值。"""
        assert SpanType.AGENT.value == "agent"
        assert SpanType.LLM.value == "llm"
        assert SpanType.TOOL.value == "tool"
        assert SpanType.HANDOFF.value == "handoff"
        assert SpanType.GUARDRAIL.value == "guardrail"

    def test_span_duration_ms_none_when_no_end(self) -> None:
        """end_time 未设置时 duration_ms 返回 None。"""
        span = Span(trace_id="t1", type=SpanType.AGENT, name="test")
        assert span.duration_ms is None

    def test_span_duration_ms_computed(self) -> None:
        """duration_ms 正确计算毫秒。"""
        from datetime import timedelta

        span = Span(trace_id="t1", type=SpanType.AGENT, name="test")
        span.end_time = span.start_time + timedelta(milliseconds=250)
        assert span.duration_ms == 250

    def test_span_duration_ms_zero(self) -> None:
        """start_time == end_time 时 duration_ms 为 0。"""
        span = Span(trace_id="t1", type=SpanType.AGENT, name="test")
        span.end_time = span.start_time
        assert span.duration_ms == 0


# ── ConsoleTraceProcessor 测试 ───────────────────────────────────


class TestConsoleTraceProcessor:
    @pytest.mark.asyncio
    async def test_lifecycle_calls(self) -> None:
        """ConsoleTraceProcessor 不应抛异常。"""
        proc = ConsoleTraceProcessor()
        trace = Trace(workflow_name="test")
        span = Span(trace_id=trace.trace_id, type=SpanType.AGENT, name="a1")

        await proc.on_trace_start(trace)
        await proc.on_span_start(span)
        await proc.on_span_end(span)
        await proc.on_trace_end(trace)


# ── Tracing 禁用测试 ─────────────────────────────────────────────


class TestTracingDisabled:
    @pytest.mark.asyncio
    async def test_no_trace_when_disabled(self) -> None:
        """tracing_enabled=False 时 RunResult.trace 应为 None。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Hi")])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "hello", config=config)

        assert result.output == "Hi"
        assert result.trace is None

    @pytest.mark.asyncio
    async def test_trace_without_processors_still_collects(self) -> None:
        """tracing_enabled=True 但无 processors 时仍产出 Trace（数据采集与通知解耦）。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Hi")])
        config = RunConfig(model_provider=provider, tracing_enabled=True, trace_processors=[])

        result = await Runner.run(agent, "hello", config=config)

        assert result.output == "Hi"
        assert result.trace is not None
        assert len(result.trace.spans) == 2  # agent + llm


# ── Runner.run() Tracing 测试 ────────────────────────────────────


class TestRunnerRunTracing:
    @pytest.mark.asyncio
    async def test_simple_chat_trace(self) -> None:
        """简单对话产出 Trace（1 agent span + 1 LLM span）。"""
        collector = CollectorProcessor()
        agent = Agent(name="echo")
        provider = MockProvider([
            ModelResponse(content="OK", token_usage=TokenUsage(10, 5, 15)),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "hi", config=config)

        assert result.output == "OK"
        assert result.trace is not None
        assert result.trace.trace_id
        assert result.trace.end_time is not None
        assert len(result.trace.spans) >= 2  # agent + llm

        # 检查 span 类型
        span_types = [s.type for s in result.trace.spans]
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types

        # 所有 span 应已完成
        for span in result.trace.spans:
            assert span.status == SpanStatus.COMPLETED
            assert span.end_time is not None

    @pytest.mark.asyncio
    async def test_trace_processor_events(self) -> None:
        """验证 TraceProcessor 收到正确的事件序列。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="done")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        await Runner.run(agent, "go", config=config)

        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"
        assert "span_start" in event_types
        assert "span_end" in event_types

    @pytest.mark.asyncio
    async def test_tool_call_creates_tool_span(self) -> None:
        """工具调用应创建 TOOL 类型 span。"""

        @function_tool()
        def get_time() -> str:
            """获取当前时间。"""
            return "12:00"

        collector = CollectorProcessor()
        agent = Agent(name="assistant", tools=[get_time])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_time", arguments="{}")],
            ),
            ModelResponse(content="It's 12:00"),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "what time?", config=config)

        assert result.output == "It's 12:00"
        assert result.trace is not None

        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert len(tool_spans) == 1
        assert tool_spans[0].name == "get_time"
        assert tool_spans[0].status == SpanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_handoff_creates_handoff_span(self) -> None:
        """Handoff 应创建 HANDOFF 类型 span。"""
        specialist = Agent(name="specialist")
        triage = Agent(name="triage", handoffs=[specialist])
        collector = CollectorProcessor()

        provider = MockProvider([
            # triage 决定 handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
            ),
            # specialist 回复
            ModelResponse(content="I'm the specialist"),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(triage, "help", config=config)

        assert result.last_agent_name == "specialist"
        assert result.trace is not None

        handoff_spans = [s for s in result.trace.spans if s.type == SpanType.HANDOFF]
        assert len(handoff_spans) == 1
        assert "triage" in handoff_spans[0].name
        assert "specialist" in handoff_spans[0].name

    @pytest.mark.asyncio
    async def test_sensitive_data_included(self) -> None:
        """trace_include_sensitive_data=True 时 span 应包含 input/output。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="secret response")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            trace_include_sensitive_data=True,
        )

        result = await Runner.run(agent, "secret input", config=config)

        assert result.trace is not None
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        assert len(llm_spans) >= 1
        # LLM span 应有 input 和 output
        assert llm_spans[0].input is not None
        assert llm_spans[0].output is not None

    @pytest.mark.asyncio
    async def test_sensitive_data_excluded(self) -> None:
        """trace_include_sensitive_data=False 时 span 不应包含 input/output。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="response")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            trace_include_sensitive_data=False,
        )

        result = await Runner.run(agent, "input", config=config)

        assert result.trace is not None
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        assert len(llm_spans) >= 1
        assert llm_spans[0].input is None
        assert llm_spans[0].output is None

    @pytest.mark.asyncio
    async def test_workflow_name_in_trace(self) -> None:
        """workflow_name 应传递到 Trace。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="ok")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            workflow_name="my_workflow",
        )

        result = await Runner.run(agent, "go", config=config)

        assert result.trace is not None
        assert result.trace.workflow_name == "my_workflow"

    @pytest.mark.asyncio
    async def test_multiple_processors(self) -> None:
        """多个 TraceProcessor 都应收到事件。"""
        c1 = CollectorProcessor()
        c2 = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="ok")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[c1, c2],
        )

        await Runner.run(agent, "go", config=config)

        assert len(c1.events) > 0
        assert len(c1.events) == len(c2.events)

    @pytest.mark.asyncio
    async def test_llm_span_has_token_usage(self) -> None:
        """LLM span 应包含 token_usage。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="ok", token_usage=TokenUsage(10, 5, 15))])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "go", config=config)

        assert result.trace is not None
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        assert len(llm_spans) >= 1
        assert llm_spans[0].token_usage is not None
        assert llm_spans[0].token_usage["total_tokens"] == 15


# ── Runner.run_streamed() Tracing 测试 ───────────────────────────


class TestRunnerStreamedTracing:
    @pytest.mark.asyncio
    async def test_streamed_trace(self) -> None:
        """流式运行也应产出完整 Trace。"""
        collector = CollectorProcessor()
        agent = Agent(name="streamer")
        provider = MockProvider([ModelResponse(content="streamed output")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result: RunResult | None = None
        async for event in Runner.run_streamed(agent, "go", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.trace is not None
        assert result.trace.trace_id
        assert result.trace.end_time is not None

        span_types = [s.type for s in result.trace.spans]
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types

    @pytest.mark.asyncio
    async def test_streamed_no_trace_when_disabled(self) -> None:
        """流式运行 tracing_enabled=False 时 trace 应为 None。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="hi")])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result: RunResult | None = None
        async for event in Runner.run_streamed(agent, "go", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.trace is None

    @pytest.mark.asyncio
    async def test_streamed_tool_span(self) -> None:
        """流式运行中工具调用也应产出 TOOL span。"""

        @function_tool()
        def add(a: int, b: int) -> str:
            """加法。"""
            return str(a + b)

        collector = CollectorProcessor()
        agent = Agent(name="calc", tools=[add])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="add", arguments='{"a": 1, "b": 2}')],
            ),
            ModelResponse(content="1+2=3"),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result: RunResult | None = None
        async for event in Runner.run_streamed(agent, "1+2=?", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                result = event.data

        assert result is not None
        assert result.trace is not None
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert len(tool_spans) == 1
        assert tool_spans[0].name == "add"


# ── 边界条件 ─────────────────────────────────────────────────────


class TestTracingEdgeCases:
    @pytest.mark.asyncio
    async def test_max_turns_exceeded_still_has_trace(self) -> None:
        """超过 max_turns 时也应返回 Trace。"""

        @function_tool()
        def noop() -> str:
            """空操作。"""
            return "done"

        collector = CollectorProcessor()
        agent = Agent(name="looper", tools=[noop])
        # 永远调用工具，不会自然结束
        provider = MockProvider([
            ModelResponse(tool_calls=[ToolCall(id="tc1", name="noop", arguments="{}")]),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "loop", config=config, max_turns=2)

        assert result.trace is not None
        assert result.trace.end_time is not None
        assert len(result.trace.spans) >= 2  # 至少有 agent + llm spans

    @pytest.mark.asyncio
    async def test_tool_error_creates_completed_span_with_error_output(self) -> None:
        """工具抛异常时 FunctionTool 内部捕获，span 状态为 COMPLETED（error 在 output 中）。"""

        @function_tool()
        def failing_tool() -> str:
            """总是失败。"""
            raise RuntimeError("boom")

        collector = CollectorProcessor()
        agent = Agent(name="bot", tools=[failing_tool])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="failing_tool", arguments="{}")],
            ),
            ModelResponse(content="tool failed"),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            trace_include_sensitive_data=True,
        )

        result = await Runner.run(agent, "do", config=config)

        assert result.trace is not None
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert len(tool_spans) == 1
        # FunctionTool 内部捕获异常返回 error string，所以 span 是 COMPLETED
        assert tool_spans[0].status == SpanStatus.COMPLETED
        # output 中包含 error 信息
        assert tool_spans[0].output is not None
        assert "Error" in str(tool_spans[0].output)
