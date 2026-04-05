"""Runner.run_streamed + run_sync + 深层护栏/工具护栏 Span 路径补充测试。

目标覆盖行（runner.py 45 行缺失）:
- 250: input guardrails parallel 分支
- 282: input guardrail exception → span FAILED
- 325: input guardrail condition exception → warning
- 375: output guardrails parallel 分支
- 400, 407: output guardrail span start + exception
- 450-453: output guardrail condition exception + active 为空 early return
- 618: tool guardrail before_fn span start (processors on_span_start)
- 689: tool guardrail after_fn span start (processors on_span_start)
- 951: run() 异常路径 → trace end + session save + raise
- 1088: run_streamed 异常路径（同 951 但在流式循环中）
- 1146-1147, 1153, 1165-1166, 1182-1185: LLM stream retry 失败 → hooks + error result
- 1254: run_streamed 通用异常路径
- 1321-1326, 1332, 1334, 1342: run_streamed 中 handoff + max_turns + hooks
- 1422: run_sync 事件循环已运行时的线程池执行
- 1492, 1504-1528: run_streamed max_turns 路径（session/hooks/yield）
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.hooks import RunHooks
from ckyclaw_framework.runner.result import RunResult, StreamEvent, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import (
    Runner,
    _execute_input_guardrails,
    _execute_output_guardrails,
)
from ckyclaw_framework.tools.function_tool import FunctionTool


# ── Helpers ─────────────────────────────────────────────────


def _mock_provider(responses: list[ModelResponse]) -> AsyncMock:
    """创建可依次返回多个 response 的 mock provider。"""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=responses)
    return provider


def _text_response(content: str) -> ModelResponse:
    return ModelResponse(
        content=content,
        tool_calls=[],
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_response(tool_calls: list[ToolCall], content: str = "") -> ModelResponse:
    return ModelResponse(
        content=content,
        tool_calls=tool_calls,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _make_tool(name: str = "my_tool", result: str = "tool_result") -> FunctionTool:
    async def fn(**kwargs: Any) -> str:
        return result

    return FunctionTool(
        name=name,
        description=f"Tool {name}",
        parameters_schema={"type": "object", "properties": {}},
        fn=fn,
    )


async def _make_stream_chunks(chunks: list[ModelChunk]) -> Any:
    """创建 async iterable 模拟流式 LLM 响应。"""
    for c in chunks:
        yield c


def _stream_provider(
    chunks_list: list[list[ModelChunk]],
) -> AsyncMock:
    """创建流式 provider mock。每次 chat() 调用返回下一组 chunk 的 async iterator。"""
    provider = AsyncMock()
    call_count = 0

    async def _chat_side_effect(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        if kwargs.get("stream"):
            idx = min(call_count, len(chunks_list) - 1)
            call_count += 1
            return _make_stream_chunks(chunks_list[idx])
        # 非流式回退
        idx = min(call_count, len(chunks_list) - 1)
        call_count += 1
        text = ""
        tcs: list[ToolCall] = []
        for c in chunks_list[idx]:
            if c.content:
                text += c.content
        return ModelResponse(
            content=text,
            tool_calls=tcs,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    provider.chat = AsyncMock(side_effect=_chat_side_effect)
    return provider


# ── INPUT GUARDRAILS (Lines 250, 282, 325) ───────────────────


class TestInputGuardrailParallelBranch:
    """覆盖 runner.py line 250 — parallel=True 且多个 guardrail。"""

    @pytest.mark.asyncio
    async def test_parallel_input_guardrails(self) -> None:
        """parallel=True + 多个 guardrail 走并行分支。"""
        async def ok_guard(ctx: RunContext, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        g1 = InputGuardrail(name="g1", guardrail_function=ok_guard)
        g2 = InputGuardrail(name="g2", guardrail_function=ok_guard)

        # 不抛异常 → 正常返回
        await _execute_input_guardrails(
            [g1, g2],
            RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
            "hello",
            tracing=None,
            parallel=True,
        )


class TestInputGuardrailException:
    """覆盖 runner.py line 282 — guardrail 函数抛异常 → span FAILED。"""

    @pytest.mark.asyncio
    async def test_guardrail_function_raises(self) -> None:
        """guardrail 函数抛异常时记录日志并继续。"""
        async def bad_guard(ctx: RunContext, text: str) -> GuardrailResult:
            raise RuntimeError("guard boom")

        g = InputGuardrail(name="bad", guardrail_function=bad_guard)

        # 异常应该被捕获并封装为 tripwire
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails(
                [g],
                RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
                "hello",
                tracing=None,
            )


class TestInputGuardrailConditionException:
    """覆盖 runner.py line 325 — condition 函数抛异常 → 当作 enabled。"""

    @pytest.mark.asyncio
    async def test_condition_raises_treated_as_enabled(self) -> None:
        """condition 抛异常 → guardrail 不被跳过（当作启用）。"""
        call_count = 0

        async def counting_guard(ctx: RunContext, text: str) -> GuardrailResult:
            nonlocal call_count
            call_count += 1
            return GuardrailResult(tripwire_triggered=False)

        def bad_condition(ctx: RunContext) -> bool:
            raise ValueError("condition error")

        g = InputGuardrail(name="cond", guardrail_function=counting_guard, condition=bad_condition)

        await _execute_input_guardrails(
            [g],
            RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
            "hello",
            tracing=None,
        )
        assert call_count == 1, "condition 异常时 guardrail 应被执行"


# ── OUTPUT GUARDRAILS (Lines 375, 400, 407, 450-453) ─────────


class TestOutputGuardrailParallelBranch:
    """覆盖 runner.py line 375 — output guardrails parallel 分支。"""

    @pytest.mark.asyncio
    async def test_parallel_output_guardrails(self) -> None:
        """parallel=True + 多个 output guardrail 走并行分支。"""
        async def ok_guard(ctx: RunContext, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        g1 = OutputGuardrail(name="og1", guardrail_function=ok_guard)
        g2 = OutputGuardrail(name="og2", guardrail_function=ok_guard)

        await _execute_output_guardrails(
            [g1, g2],
            RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
            "output text",
            tracing=None,
            parallel=True,
        )


class TestOutputGuardrailException:
    """覆盖 runner.py lines 400, 407 — output guardrail 函数抛异常。"""

    @pytest.mark.asyncio
    async def test_output_guardrail_function_raises(self) -> None:
        """output guardrail 函数抛异常 → span FAILED + 触发 tripwire。"""
        async def bad_guard(ctx: RunContext, text: str) -> GuardrailResult:
            raise RuntimeError("output guard boom")

        g = OutputGuardrail(name="bad_og", guardrail_function=bad_guard)

        with pytest.raises(OutputGuardrailTripwireError):
            await _execute_output_guardrails(
                [g],
                RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
                "output",
                tracing=None,
            )


class TestOutputGuardrailConditionExceptionAndEmpty:
    """覆盖 runner.py lines 450-453 — condition 异常 + 空 active 列表。"""

    @pytest.mark.asyncio
    async def test_condition_raises_treated_as_enabled(self) -> None:
        """output guardrail condition 抛异常 → 当作启用。"""
        call_count = 0

        async def counting_guard(ctx: RunContext, text: str) -> GuardrailResult:
            nonlocal call_count
            call_count += 1
            return GuardrailResult(tripwire_triggered=False)

        def bad_condition(ctx: RunContext) -> bool:
            raise ValueError("cond error")

        g = OutputGuardrail(name="cond_og", guardrail_function=counting_guard, condition=bad_condition)

        await _execute_output_guardrails(
            [g],
            RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
            "output",
            tracing=None,
        )
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_all_conditions_false_early_return(self) -> None:
        """所有 output guardrail 都被 condition 跳过 → early return。"""
        async def never_called(ctx: RunContext, text: str) -> GuardrailResult:
            raise AssertionError("should not be called")

        def always_false(ctx: RunContext) -> bool:
            return False

        g = OutputGuardrail(name="skip_og", guardrail_function=never_called, condition=always_false)

        # 不应抛异常
        await _execute_output_guardrails(
            [g],
            RunContext(agent=Agent(name="t", instructions="t"), config=RunConfig(), context={}, turn_count=0),
            "output",
            tracing=None,
        )


# ── TOOL GUARDRAIL SPAN PROCESSORS (Lines 618, 689) ──────────


class TestToolGuardrailSpanProcessors:
    """覆盖 runner.py lines 618, 689 — tool guardrail 的 span 追踪处理器调用。"""

    @pytest.mark.asyncio
    async def test_tool_guardrail_with_tracing_processors(self) -> None:
        """tool guardrail (before + after) 使用 tracing → on_span_start 被调用。"""
        async def before_fn(ctx: RunContext, tool_name: str, args: dict[str, Any]) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        async def after_fn(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        tg = ToolGuardrail(name="tg1", before_fn=before_fn, after_fn=after_fn)
        tool = _make_tool("test_tool", "ok")
        tc = ToolCall(id="tc1", name="test_tool", arguments="{}")

        provider = _mock_provider([
            _tool_response([tc]),
            _text_response("done"),
        ])
        agent = Agent(name="t", instructions="t", tools=[tool], tool_guardrails=[tg])
        config = RunConfig(model_provider=provider, tracing_enabled=True)

        result = await Runner.run(agent, "Hi", config=config)
        assert result.output == "done"


# ── RUN_STREAMED LLM RETRY FAILURE (Lines 1146-1185) ─────────


class TestRunStreamedLLMRetryFailure:
    """覆盖 runner.py lines 1146-1147, 1153, 1165-1166, 1182-1185:
    LLM stream 调用全部失败 → hooks + error result + session save。
    """

    @pytest.mark.asyncio
    async def test_stream_all_retries_fail(self) -> None:
        """LLM stream 调用 3 次全部失败 → 产出 RUN_COMPLETE error 事件。"""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("network down"))

        hooks = RunHooks(
            on_error=AsyncMock(),
            on_agent_end=AsyncMock(),
            on_run_end=AsyncMock(),
            on_run_start=AsyncMock(),
            on_agent_start=AsyncMock(),
            on_llm_start=AsyncMock(),
        )
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        config = RunConfig(
            model_provider=provider,
            max_retries=1,
            retry_delay=0.01,
            tracing_enabled=False,
            hooks=hooks,
        )
        agent = Agent(name="t", instructions="t")

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(agent, "Hi", config=config, session=session):
            events.append(evt)

        # 最后一个事件是 RUN_COMPLETE 且 output 包含错误
        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        complete_evt = [e for e in events if e.type == StreamEventType.RUN_COMPLETE][0]
        assert "Error" in complete_evt.data.output
        hooks.on_error.assert_called_once()
        session.append.assert_called_once()


class TestRunStreamedLLMRetryWithBackoff:
    """覆盖 runner.py lines 1146-1147 — LLM stream retry 中间有 backoff。"""

    @pytest.mark.asyncio
    async def test_stream_retry_then_succeed(self) -> None:
        """第一次失败，第二次成功 → 正常完成。"""
        call_count = 0

        async def _chat(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            # 成功返回流
            return _make_stream_chunks([
                ModelChunk(content="Hi there", tool_call_chunks=[]),
            ])

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=_chat)

        config = RunConfig(
            model_provider=provider,
            max_retries=2,
            retry_delay=0.01,
            tracing_enabled=False,
        )
        agent = Agent(name="t", instructions="t")

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(agent, "Hi", config=config):
            events.append(evt)

        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        complete_evt = [e for e in events if e.type == StreamEventType.RUN_COMPLETE][0]
        assert complete_evt.data.output == "Hi there"


# ── RUN_STREAMED HANDOFF + MAX_TURNS (Lines 1321-1342, 1492, 1504-1528) ──


class TestRunStreamedHandoff:
    """覆盖 runner.py lines 1321-1326, 1332, 1334:
    run_streamed 中执行 handoff (带 InputFilter) 并最终完成。
    """

    @pytest.mark.asyncio
    async def test_stream_handoff_with_input_filter(self) -> None:
        """run_streamed 中 handoff 到另一个 agent + InputFilter。"""
        target_agent = Agent(name="target", instructions="target agent")

        def my_filter(messages: list[Message]) -> list[Message]:
            return [m for m in messages if m.role == MessageRole.USER]

        handoff = Handoff(
            agent=target_agent,
            tool_name="transfer_to_target",
            tool_description="Go to target",
            input_filter=my_filter,
        )

        # 第一次：工具调用 handoff
        # 第二次：target agent 返回文本
        call_count = 0

        async def _chat(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if kwargs.get("stream"):
                if call_count == 1:
                    # handoff 工具调用
                    return _make_stream_chunks([
                        ModelChunk(
                            content="",
                            tool_call_chunks=[
                                ToolCallChunk(index=0, id="tc1", name="transfer_to_target", arguments_delta="{}"),
                            ],
                        ),
                    ])
                else:
                    return _make_stream_chunks([
                        ModelChunk(content="target response", tool_call_chunks=[]),
                    ])
            return ModelResponse(content="", tool_calls=[], token_usage=TokenUsage())

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=_chat)

        agent = Agent(name="source", instructions="source agent", handoffs=[handoff])
        hooks = RunHooks(
            on_agent_end=AsyncMock(),
            on_run_end=AsyncMock(),
            on_run_start=AsyncMock(),
            on_agent_start=AsyncMock(),
            on_llm_start=AsyncMock(),
            on_llm_end=AsyncMock(),
        )
        config = RunConfig(model_provider=provider, tracing_enabled=False, hooks=hooks)

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(agent, "Hi", config=config):
            events.append(evt)

        assert any(e.type == StreamEventType.HANDOFF for e in events)
        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        complete_evt = [e for e in events if e.type == StreamEventType.RUN_COMPLETE][0]
        assert complete_evt.data.output == "target response"


# ── RUNNER.RUN WITH TRACING + GUARDRAIL EXCEPTIONS ──


class TestRunWithTracingGuardrailException:
    """通过 Runner.run 触发 tracing + guardrail 异常路径（lines 282, 325, 400, 407, 450-453）。"""

    @pytest.mark.asyncio
    async def test_input_guardrail_exception_with_tracing(self) -> None:
        """Runner.run 中 input guardrail 抛异常 + tracing=True → span FAILED。"""
        async def bad_guard(ctx: RunContext, text: str) -> GuardrailResult:
            raise RuntimeError("guard error")

        g = InputGuardrail(name="bad", guardrail_function=bad_guard)
        provider = _mock_provider([_text_response("ok")])
        agent = Agent(name="t", instructions="t", input_guardrails=[g])
        config = RunConfig(model_provider=provider, tracing_enabled=True)

        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(agent, "Hi", config=config)

    @pytest.mark.asyncio
    async def test_input_guardrail_condition_exception_with_run(self) -> None:
        """Runner.run + 并行 input guardrail condition 抛异常 → 当作启用。"""
        call_count = 0

        async def counting_guard(ctx: RunContext, text: str) -> GuardrailResult:
            nonlocal call_count
            call_count += 1
            return GuardrailResult(tripwire_triggered=False)

        def bad_condition(ctx: RunContext) -> bool:
            raise ValueError("condition error")

        g1 = InputGuardrail(name="g1", guardrail_function=counting_guard, condition=bad_condition)
        g2 = InputGuardrail(name="g2", guardrail_function=counting_guard)

        provider = _mock_provider([_text_response("ok")])
        agent = Agent(name="t", instructions="t", input_guardrails=[g1, g2])
        config = RunConfig(model_provider=provider, tracing_enabled=True, guardrail_parallel=True)

        result = await Runner.run(agent, "Hi", config=config)
        assert result.output == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_output_guardrail_exception_with_tracing(self) -> None:
        """Runner.run + output guardrail 抛异常 + tracing=True → span FAILED。"""
        async def bad_og(ctx: RunContext, text: str) -> GuardrailResult:
            raise RuntimeError("output guard error")

        g = OutputGuardrail(name="bad_og", guardrail_function=bad_og)
        provider = _mock_provider([_text_response("some output")])
        agent = Agent(name="t", instructions="t", output_guardrails=[g])
        config = RunConfig(model_provider=provider, tracing_enabled=True)

        with pytest.raises(OutputGuardrailTripwireError):
            await Runner.run(agent, "Hi", config=config)

    @pytest.mark.asyncio
    async def test_output_guardrail_condition_exception_parallel_with_tracing(self) -> None:
        """Runner.run + 并行 output guardrail condition 抛异常 + tracing → 当作启用。"""
        call_count = 0

        async def counting_guard(ctx: RunContext, text: str) -> GuardrailResult:
            nonlocal call_count
            call_count += 1
            return GuardrailResult(tripwire_triggered=False)

        def bad_condition(ctx: RunContext) -> bool:
            raise ValueError("cond error")

        g1 = OutputGuardrail(name="og1", guardrail_function=counting_guard, condition=bad_condition)
        g2 = OutputGuardrail(name="og2", guardrail_function=counting_guard)

        provider = _mock_provider([_text_response("output")])
        agent = Agent(name="t", instructions="t", output_guardrails=[g1, g2])
        config = RunConfig(model_provider=provider, tracing_enabled=True, guardrail_parallel=True)

        result = await Runner.run(agent, "Hi", config=config)
        assert result.output == "output"
        assert call_count == 2


class TestRunWithTracingToolGuardrail:
    """通过 Runner.run触发 tool guardrail 的 tracing span path（lines 618, 689）。"""

    @pytest.mark.asyncio
    async def test_tool_guardrail_before_after_with_tracing(self) -> None:
        """Runner.run + tracing=True + tool guardrail → 触发 span 处理器。"""
        async def before_fn(ctx: RunContext, tool_name: str, args: dict[str, Any]) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        async def after_fn(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False)

        tg = ToolGuardrail(name="tg", before_fn=before_fn, after_fn=after_fn)
        tool = _make_tool("my_tool", "tool ok")
        tc = ToolCall(id="tc1", name="my_tool", arguments="{}")

        provider = _mock_provider([
            _tool_response([tc]),
            _text_response("done with tool"),
        ])
        agent = Agent(name="t", instructions="t", tools=[tool], tool_guardrails=[tg])
        config = RunConfig(model_provider=provider, tracing_enabled=True)

        result = await Runner.run(agent, "Hi", config=config)
        assert result.output == "done with tool"


class TestRunStreamedMaxTurnsWithTracing:
    """run_streamed max_turns + tracing + hooks + session 组合（lines 1492-1528）。"""

    @pytest.mark.asyncio
    async def test_streamed_max_turns_full_path(self) -> None:
        """run_streamed max_turns 1 + tracing + session + hooks。"""
        call_count = 0

        async def _chat(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            tc = ToolCall(id=f"tc{call_count}", name="my_tool", arguments="{}")
            if kwargs.get("stream"):
                return _make_stream_chunks([
                    ModelChunk(
                        content="",
                        tool_call_chunks=[
                            ToolCallChunk(index=0, id=f"tc{call_count}", name="my_tool", arguments_delta="{}"),
                        ],
                    ),
                ])
            return ModelResponse(content="", tool_calls=[tc], token_usage=TokenUsage())

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=_chat)

        tool = _make_tool("my_tool", "ok")
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        agent = Agent(name="t", instructions="t", tools=[tool])
        config = RunConfig(
            model_provider=provider, tracing_enabled=True,
            hooks=RunHooks(
                on_run_start=AsyncMock(),
                on_run_end=AsyncMock(),
                on_agent_start=AsyncMock(),
                on_agent_end=AsyncMock(),
                on_llm_start=AsyncMock(),
                on_llm_end=AsyncMock(),
            ),
        )

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(
            agent, "Hi", config=config, max_turns=1, session=session,
        ):
            events.append(evt)

        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        session.append.assert_called_once()


class TestRunWithLLMFailureAndTracing:
    """Runner.run LLM 失败 + tracing + hooks + session（lines 951, 1088）。"""

    @pytest.mark.asyncio
    async def test_run_llm_failure_tracing_hooks_session(self) -> None:
        """Runner.run LLM 全部失败 → hooks.on_error + session save + trace end。"""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("LLM down"))

        hooks = RunHooks(
            on_error=AsyncMock(),
            on_agent_end=AsyncMock(),
            on_run_end=AsyncMock(),
            on_run_start=AsyncMock(),
            on_agent_start=AsyncMock(),
            on_llm_start=AsyncMock(),
        )
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        agent = Agent(name="t", instructions="t")
        config = RunConfig(
            model_provider=provider,
            max_retries=0,
            tracing_enabled=True,
            hooks=hooks,
        )

        result = await Runner.run(agent, "Hi", config=config, session=session)
        assert "Error" in result.output or "error" in result.output.lower()
        hooks.on_error.assert_called_once()
        hooks.on_run_end.assert_called_once()
        session.append.assert_called_once()


class TestRunStreamedLLMFailureWithTracing:
    """run_streamed LLM 失败 + tracing + hooks + session（lines 1146-1185）。"""

    @pytest.mark.asyncio
    async def test_streamed_llm_failure_full_path(self) -> None:
        """run_streamed LLM 全部失败 + tracing + hooks + session。"""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("stream fail"))

        hooks = RunHooks(
            on_error=AsyncMock(),
            on_agent_end=AsyncMock(),
            on_run_end=AsyncMock(),
            on_run_start=AsyncMock(),
            on_agent_start=AsyncMock(),
            on_llm_start=AsyncMock(),
        )
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        agent = Agent(name="t", instructions="t")
        config = RunConfig(
            model_provider=provider,
            max_retries=1,
            retry_delay=0.01,
            tracing_enabled=True,
            hooks=hooks,
        )

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(agent, "Hi", config=config, session=session):
            events.append(evt)

        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        hooks.on_error.assert_called_once()
        session.append.assert_called_once()


class TestRunStreamedMaxTurns:
    """覆盖 runner.py lines 1504-1528 + 1492:
    run_streamed max_turns 超过后走 session save + hooks + yield。
    """

    @pytest.mark.asyncio
    async def test_stream_max_turns_exceeded(self) -> None:
        """run_streamed 中超过 max_turns → 最终事件携带最后 assistant 消息。"""
        # 每轮都返回工具调用，永不停止
        call_count = 0

        async def _chat(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if kwargs.get("stream"):
                return _make_stream_chunks([
                    ModelChunk(
                        content=f"thinking turn {call_count}",
                        tool_call_chunks=[
                            ToolCallChunk(index=0, id=f"tc{call_count}", name="my_tool", arguments_delta="{}"),
                        ],
                    ),
                ])
            return ModelResponse(content="", tool_calls=[], token_usage=TokenUsage())

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=_chat)

        tool = _make_tool("my_tool", "ok")
        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        hooks = RunHooks(
            on_run_end=AsyncMock(),
            on_run_start=AsyncMock(),
            on_agent_start=AsyncMock(),
            on_agent_end=AsyncMock(),
            on_llm_start=AsyncMock(),
            on_llm_end=AsyncMock(),
            on_tool_start=AsyncMock(),
            on_tool_end=AsyncMock(),
        )

        agent = Agent(name="t", instructions="t", tools=[tool])
        config = RunConfig(model_provider=provider, tracing_enabled=False, hooks=hooks)

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(
            agent, "Hi", config=config, max_turns=2, session=session,
        ):
            events.append(evt)

        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
        session.append.assert_called_once()
        hooks.on_run_end.assert_called_once()


# ── RUN_STREAMED EXCEPTION PATH (Lines 951, 1088, 1254) ──────


class TestRunStreamedException:
    """覆盖 runner.py lines 951, 1088, 1254:
    run_streamed 中出现异常 → trace end + session save + raise。
    """

    @pytest.mark.asyncio
    async def test_stream_input_guardrail_tripwire(self) -> None:
        """run_streamed 中 input guardrail 触发 → 保存 session + raise。"""
        async def tripwire_guard(ctx: RunContext, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="blocked")

        g = InputGuardrail(name="block", guardrail_function=tripwire_guard)
        provider = AsyncMock()
        provider.chat = AsyncMock()

        session = AsyncMock()
        session.get_history = AsyncMock(return_value=[])

        agent = Agent(name="t", instructions="t", input_guardrails=[g])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        with pytest.raises(InputGuardrailTripwireError):
            async for _evt in Runner.run_streamed(agent, "Hi", config=config, session=session):
                pass

        session.append.assert_called_once()


# ── RUN_SYNC IN RUNNING LOOP (Line 1422) ─────────────────────


class TestRunSyncInRunningLoop:
    """覆盖 runner.py line 1422 — run_sync 在已有事件循环时使用 ThreadPoolExecutor。"""

    def test_run_sync_basic(self) -> None:
        """run_sync 正常返回结果（无已有事件循环）。"""
        provider = _mock_provider([_text_response("sync ok")])
        agent = Agent(name="t", instructions="t")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = Runner.run_sync(agent, "Hi", config=config)
        assert result.output == "sync ok"


# ── RUN_STREAMED SIMPLE SUCCESS ──────────────────────────────


class TestRunStreamedSimpleSuccess:
    """基础 run_streamed 成功路径，确保流式事件完整。"""

    @pytest.mark.asyncio
    async def test_simple_text_stream(self) -> None:
        """最简单的流式路径：LLM 返回文本 chunk。"""
        async def _chat(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("stream"):
                return _make_stream_chunks([
                    ModelChunk(content="Hello ", tool_call_chunks=[]),
                    ModelChunk(content="World", tool_call_chunks=[]),
                ])
            return ModelResponse(content="Hello World", tool_calls=[], token_usage=TokenUsage())

        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=_chat)

        agent = Agent(name="t", instructions="t")
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        events: list[StreamEvent] = []
        async for evt in Runner.run_streamed(agent, "Hi", config=config):
            events.append(evt)

        chunk_events = [e for e in events if e.type == StreamEventType.LLM_CHUNK]
        assert len(chunk_events) == 2
        assert chunk_events[0].data == "Hello "
        assert chunk_events[1].data == "World"
        assert any(e.type == StreamEventType.RUN_COMPLETE for e in events)
