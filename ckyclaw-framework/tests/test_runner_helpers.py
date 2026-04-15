"""Runner 辅助函数单元测试 — 覆盖 _build_trim_config / _parse_structured_output / _resolve_* / _find_* / _normalize_input / _accumulate_usage / _build_response_format / _build_system_message / _build_tool_schemas / _TracingCtx。"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import (
    _accumulate_usage,
    _build_response_format,
    _build_system_message,
    _build_tool_schemas,
    _build_trim_config,
    _find_handoff_target,
    _find_tool,
    _normalize_input,
    _parse_structured_output,
    _resolve_model,
    _resolve_provider,
    _resolve_settings,
    _TracingCtx,
)
from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimStrategy
from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tracing.span import SpanStatus, SpanType

# ── 辅助 fixtures ──────────────────────────────────────────────

class SampleOutput(BaseModel):
    """用于测试结构化输出解析的 Pydantic 模型。"""
    name: str
    score: int


def _make_agent(**kwargs: Any) -> Agent:
    """快捷创建测试 Agent。"""
    defaults: dict[str, Any] = {"name": "test_agent", "instructions": "test"}
    defaults.update(kwargs)
    return Agent(**defaults)


# ─── _build_trim_config ─────────────────────────────────────────

class TestBuildTrimConfig:
    """_build_trim_config 测试。"""

    def test_returns_none_when_both_none(self) -> None:
        """两个字段都为 None 时返回 None（line 95）。"""
        config = RunConfig(max_history_tokens=None, max_history_messages=None)
        assert _build_trim_config(config) is None

    def test_returns_config_with_tokens(self) -> None:
        """仅 max_history_tokens 非 None。"""
        config = RunConfig(max_history_tokens=4000)
        result = _build_trim_config(config)
        assert result is not None
        assert isinstance(result, HistoryTrimConfig)
        assert result.max_history_tokens == 4000
        assert result.strategy == HistoryTrimStrategy.TOKEN_BUDGET

    def test_returns_config_with_messages(self) -> None:
        """仅 max_history_messages 非 None。"""
        config = RunConfig(max_history_messages=50)
        result = _build_trim_config(config)
        assert result is not None
        assert result.max_history_messages == 50

    def test_strategy_override(self) -> None:
        """手动指定 strategy。"""
        config = RunConfig(
            max_history_tokens=4000,
            history_trim_strategy=HistoryTrimStrategy.SLIDING_WINDOW,
        )
        result = _build_trim_config(config)
        assert result is not None
        assert result.strategy == HistoryTrimStrategy.SLIDING_WINDOW


# ─── _parse_structured_output ────────────────────────────────────

class TestParseStructuredOutput:
    """_parse_structured_output 测试。"""

    def test_none_output_type_returns_raw(self) -> None:
        """output_type 为 None 时直接返回原始文本。"""
        assert _parse_structured_output("hello", None) == "hello"

    def test_empty_raw_returns_raw(self) -> None:
        """raw 为空字符串时直接返回。"""
        assert _parse_structured_output("", SampleOutput) == ""

    def test_valid_json_pydantic(self) -> None:
        """有效 JSON → Pydantic 模型。"""
        raw = json.dumps({"name": "alice", "score": 99})
        result = _parse_structured_output(raw, SampleOutput)
        assert isinstance(result, SampleOutput)
        assert result.name == "alice"
        assert result.score == 99

    def test_json_embedded_in_text(self) -> None:
        """文本中嵌入的 JSON 块 → fallback 提取。"""
        raw = 'Some text before {"name": "bob", "score": 88} some text after'
        result = _parse_structured_output(raw, SampleOutput)
        assert isinstance(result, SampleOutput)
        assert result.name == "bob"

    def test_invalid_json_returns_raw(self) -> None:
        """无法解析 → 返回原始文本。"""
        result = _parse_structured_output("not json at all", SampleOutput)
        assert result == "not json at all"

    def test_non_pydantic_output_type(self) -> None:
        """非 Pydantic 的 output_type 直接返回原始文本。"""
        assert _parse_structured_output("hello", str) == "hello"


# ─── _build_response_format ──────────────────────────────────────

class TestBuildResponseFormat:
    """_build_response_format 测试。"""

    def test_none_output_type(self) -> None:
        assert _build_response_format(None) is None

    def test_pydantic_model(self) -> None:
        fmt = _build_response_format(SampleOutput)
        assert fmt is not None
        assert fmt["type"] == "json_schema"
        assert fmt["json_schema"]["name"] == "SampleOutput"

    def test_dict_type(self) -> None:
        fmt = _build_response_format({"type": "object"})  # type: ignore[arg-type]
        assert fmt == {"type": "json_object"}

    def test_plain_type_returns_none(self) -> None:
        assert _build_response_format(int) is None  # type: ignore[arg-type]


# ─── _resolve_* ─────────────────────────────────────────────────

class TestResolvers:
    """_resolve_model / _resolve_settings / _resolve_provider 测试。"""

    def test_resolve_model_config_override(self) -> None:
        agent = _make_agent(model="gpt-4")
        config = RunConfig(model="gpt-3.5-turbo")
        assert _resolve_model(agent, config) == "gpt-3.5-turbo"

    def test_resolve_model_agent_default(self) -> None:
        agent = _make_agent(model="gpt-4")
        assert _resolve_model(agent, None) == "gpt-4"

    def test_resolve_model_fallback(self) -> None:
        agent = _make_agent(model=None)
        assert _resolve_model(agent, RunConfig()) == "gpt-4o-mini"

    def test_resolve_settings_config_override(self) -> None:
        ms = ModelSettings(temperature=0.5)
        config = RunConfig(model_settings=ms)
        agent = _make_agent(model_settings=ModelSettings(temperature=0.9))
        assert _resolve_settings(agent, config) is ms

    def test_resolve_settings_agent_default(self) -> None:
        ms = ModelSettings(temperature=0.9)
        agent = _make_agent(model_settings=ms)
        assert _resolve_settings(agent, None) is ms

    def test_resolve_settings_none(self) -> None:
        agent = _make_agent()
        assert _resolve_settings(agent, RunConfig()) is None

    def test_resolve_provider_custom(self) -> None:
        mock_provider = MagicMock()
        config = RunConfig(model_provider=mock_provider)
        assert _resolve_provider(config) is mock_provider

    def test_resolve_provider_default(self) -> None:
        provider = _resolve_provider(RunConfig())
        assert isinstance(provider, LiteLLMProvider)

    def test_resolve_provider_none_config(self) -> None:
        provider = _resolve_provider(None)
        assert isinstance(provider, LiteLLMProvider)


# ─── _normalize_input ────────────────────────────────────────────

class TestNormalizeInput:
    """_normalize_input 测试。"""

    def test_string_input(self) -> None:
        msgs = _normalize_input("hello")
        assert len(msgs) == 1
        assert msgs[0].role == MessageRole.USER
        assert msgs[0].content == "hello"

    def test_message_list(self) -> None:
        original = [Message(role=MessageRole.USER, content="hi")]
        result = _normalize_input(original)
        assert result == original
        assert result is not original  # 应该是新列表


# ─── _accumulate_usage ───────────────────────────────────────────

class TestAccumulateUsage:
    """_accumulate_usage 测试。"""

    def test_accumulate(self) -> None:
        total = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        delta = TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)
        _accumulate_usage(total, delta)
        assert total.prompt_tokens == 13
        assert total.completion_tokens == 7
        assert total.total_tokens == 20

    def test_none_delta(self) -> None:
        total = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        _accumulate_usage(total, None)
        assert total.prompt_tokens == 10


# ─── _find_tool / _find_handoff_target ───────────────────────────

class TestFindToolAndHandoff:
    """_find_tool / _find_handoff_target 测试。"""

    def test_find_tool_found(self) -> None:
        tool = FunctionTool(name="my_tool", description="d", parameters_schema={}, fn=AsyncMock())
        agent = _make_agent(tools=[tool])
        assert _find_tool(agent, "my_tool") is tool

    def test_find_tool_not_found(self) -> None:
        agent = _make_agent(tools=[])
        assert _find_tool(agent, "my_tool") is None

    def test_find_handoff_target_agent(self) -> None:
        target = _make_agent(name="agent_b")
        src = _make_agent(name="agent_a", handoffs=[target])
        result = _find_handoff_target(src, "transfer_to_agent_b")
        assert result is not None
        assert result[0] is target
        assert result[1] is None

    def test_find_handoff_target_not_found(self) -> None:
        agent = _make_agent(handoffs=[])
        assert _find_handoff_target(agent, "transfer_to_xxx") is None


# ─── _build_system_message ─────────────────────────────────────

class TestBuildSystemMessage:
    """_build_system_message 测试。"""

    @pytest.mark.asyncio
    async def test_static_instructions(self) -> None:
        agent = _make_agent(instructions="Be helpful.")
        ctx = RunContext(agent=agent, config=RunConfig(), context={})
        msg = await _build_system_message(agent, ctx)
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "Be helpful."

    @pytest.mark.asyncio
    async def test_callable_instructions(self) -> None:
        agent = _make_agent(instructions=lambda ctx: f"Turn {ctx.turn_count}")
        ctx = RunContext(agent=agent, config=RunConfig(), context={}, turn_count=3)
        msg = await _build_system_message(agent, ctx)
        assert "Turn 3" in msg.content

    @pytest.mark.asyncio
    async def test_async_callable_instructions(self) -> None:
        async def dynamic(ctx: RunContext) -> str:
            return "async instructions"

        agent = _make_agent(instructions=dynamic)
        ctx = RunContext(agent=agent, config=RunConfig(), context={})
        msg = await _build_system_message(agent, ctx)
        assert msg.content == "async instructions"

    @pytest.mark.asyncio
    async def test_output_type_appends_schema_hint(self) -> None:
        agent = _make_agent(output_type=SampleOutput)
        ctx = RunContext(agent=agent, config=RunConfig(), context={})
        msg = await _build_system_message(agent, ctx)
        assert "JSON Schema" in msg.content
        assert "SampleOutput" in msg.content or "name" in msg.content

    @pytest.mark.asyncio
    async def test_none_instructions(self) -> None:
        agent = _make_agent(instructions=None)
        ctx = RunContext(agent=agent, config=RunConfig(), context={})
        msg = await _build_system_message(agent, ctx)
        assert msg.content is not None  # 至少返回空字符串


# ─── _build_tool_schemas ─────────────────────────────────────────

class TestBuildToolSchemas:
    """_build_tool_schemas 测试。"""

    def test_empty_tools(self) -> None:
        agent = _make_agent(tools=[])
        assert _build_tool_schemas(agent) == []

    def test_basic_tool(self) -> None:
        tool = FunctionTool(
            name="greet",
            description="Say hello",
            parameters_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            fn=AsyncMock(),
        )
        agent = _make_agent(tools=[tool])
        schemas = _build_tool_schemas(agent)
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "greet"

    def test_tool_with_condition_false(self) -> None:
        """condition 返回 False 时工具被过滤。"""
        tool = FunctionTool(
            name="secret",
            description="d",
            parameters_schema={},
            fn=AsyncMock(),
            condition=lambda ctx: False,
        )
        agent = _make_agent(tools=[tool])
        ctx = RunContext(agent=agent, config=RunConfig(), context={})
        schemas = _build_tool_schemas(agent, ctx)
        assert len(schemas) == 0

    def test_handoff_agent(self) -> None:
        """Handoff 目标是 Agent 实例。"""
        target = _make_agent(name="helper", description="Helps with stuff")
        agent = _make_agent(handoffs=[target])
        schemas = _build_tool_schemas(agent)
        assert any("transfer_to_helper" in s["function"]["name"] for s in schemas)


# ─── _TracingCtx ─────────────────────────────────────────────────

class TestTracingCtx:
    """_TracingCtx 内部 Tracing 上下文管理器测试。"""

    @pytest.mark.asyncio
    async def test_disabled_noop(self) -> None:
        """tracing_enabled=False 时所有操作为空。"""
        config = RunConfig(tracing_enabled=False)
        ctx = _TracingCtx(config, "agent_a")
        assert not ctx.active
        await ctx.start_trace("wf")
        assert ctx.trace is None
        result = await ctx.end_trace()
        assert result is None

    @pytest.mark.asyncio
    async def test_enabled_lifecycle(self) -> None:
        """完整生命周期: start_trace → spans → end_trace。"""
        processor = AsyncMock()
        config = RunConfig(tracing_enabled=True, trace_processors=[processor])
        ctx = _TracingCtx(config, "agent_a")
        assert ctx.active

        await ctx.start_trace("my_workflow")
        assert ctx.trace is not None
        assert ctx.trace.workflow_name == "my_workflow"
        processor.on_trace_start.assert_awaited_once()

        # Agent Span
        agent_span = await ctx.start_agent_span("agent_a")
        assert agent_span.type == SpanType.AGENT
        assert agent_span.name == "agent_a"
        processor.on_span_start.assert_awaited()

        # LLM Span
        llm_span = await ctx.start_llm_span("gpt-4")
        assert llm_span.type == SpanType.LLM
        assert llm_span.parent_span_id == agent_span.span_id

        # End LLM Span
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        await ctx.end_span(llm_span, output="response text", token_usage=usage)
        assert llm_span.status == SpanStatus.COMPLETED
        assert llm_span.token_usage is not None
        assert llm_span.token_usage["total_tokens"] == 15

        # Tool Span
        tool_span = await ctx.start_tool_span("my_tool", {"arg1": "val1"})
        assert tool_span.type == SpanType.TOOL
        assert tool_span.input == {"arg1": "val1"}
        await ctx.end_span(tool_span, output="tool result")

        # Handoff Span
        handoff_span = await ctx.handoff_span("agent_a", "agent_b")
        assert handoff_span.type == SpanType.HANDOFF
        assert handoff_span.status == SpanStatus.COMPLETED
        assert handoff_span.metadata["from"] == "agent_a"

        # End Agent Span
        await ctx.end_span(agent_span)

        # End Trace
        trace = await ctx.end_trace()
        assert trace is not None
        assert trace.end_time is not None
        processor.on_trace_end.assert_awaited_once()
        # Spans 总数: agent + llm + tool + handoff = 4
        assert len(trace.spans) == 4

    @pytest.mark.asyncio
    async def test_sensitive_data_excluded(self) -> None:
        """include_sensitive=False 时不记录输入输出。"""
        config = RunConfig(
            tracing_enabled=True,
            trace_include_sensitive_data=False,
        )
        ctx = _TracingCtx(config, "agent")
        await ctx.start_trace("wf")

        llm_span = await ctx.start_llm_span(
            "gpt-4",
            [Message(role=MessageRole.USER, content="secret data")],
        )
        assert llm_span.input is None  # 未记录

        await ctx.end_span(llm_span, output="secret output")
        assert llm_span.output is None  # 未记录

        tool_span = await ctx.start_tool_span("my_tool", {"key": "val"})
        assert tool_span.input is None  # 未记录

    @pytest.mark.asyncio
    async def test_end_span_failed_status(self) -> None:
        """end_span 可指定 FAILED 状态。"""
        config = RunConfig(tracing_enabled=True)
        ctx = _TracingCtx(config, "agent")
        await ctx.start_trace("wf")

        span = await ctx.start_agent_span("agent")
        await ctx.end_span(span, status=SpanStatus.FAILED)
        assert span.status == SpanStatus.FAILED

    @pytest.mark.asyncio
    async def test_no_trace_spans_still_work(self) -> None:
        """trace 未初始化时 span 仍可创建（trace_id 为空串）。"""
        config = RunConfig(tracing_enabled=True)
        ctx = _TracingCtx(config, "agent")
        # 不调用 start_trace
        span = await ctx.start_agent_span("agent")
        assert span.trace_id == ""

    @pytest.mark.asyncio
    async def test_output_truncation(self) -> None:
        """字符串 output 超过 1000 字符时被截断。"""
        config = RunConfig(tracing_enabled=True, trace_include_sensitive_data=True)
        ctx = _TracingCtx(config, "agent")
        await ctx.start_trace("wf")
        span = await ctx.start_agent_span("agent")

        long_output = "x" * 2000
        await ctx.end_span(span, output=long_output)
        assert len(span.output) == 1000
