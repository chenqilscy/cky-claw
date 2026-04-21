"""Runner Guardrail 执行函数单元测试 — 覆盖 _execute_input_guardrails / _execute_output_guardrails / 并行模式 / condition / tracing。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from kasaya.agent.agent import Agent
from kasaya.guardrails.input_guardrail import InputGuardrail
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from kasaya.runner.run_config import RunConfig
from kasaya.runner.run_context import RunContext
from kasaya.runner.runner import (
    _execute_input_guardrails,
    _execute_input_guardrails_parallel,
    _execute_output_guardrails,
    _execute_output_guardrails_parallel,
    _TracingCtx,
)
from kasaya.tracing.span import SpanStatus


def _ctx() -> RunContext:
    """创建测试用 RunContext。"""
    agent = Agent(name="test", instructions="test")
    return RunContext(agent=agent, config=RunConfig(), context={})


def _safe_guardrail(name: str = "safe", **kwargs: Any) -> InputGuardrail:
    """创建通过的 InputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        return GuardrailResult(tripwire_triggered=False, message="ok")
    return InputGuardrail(name=name, guardrail_function=fn, **kwargs)


def _trip_guardrail(name: str = "trip", **kwargs: Any) -> InputGuardrail:
    """创建触发的 InputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        return GuardrailResult(tripwire_triggered=True, message="blocked")
    return InputGuardrail(name=name, guardrail_function=fn, **kwargs)


def _error_guardrail(name: str = "err", **kwargs: Any) -> InputGuardrail:
    """创建抛异常的 InputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        raise RuntimeError("guardrail boom")
    return InputGuardrail(name=name, guardrail_function=fn, **kwargs)


def _safe_output_guardrail(name: str = "safe_out") -> OutputGuardrail:
    """创建通过的 OutputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        return GuardrailResult(tripwire_triggered=False, message="ok")
    return OutputGuardrail(name=name, guardrail_function=fn)


def _trip_output_guardrail(name: str = "trip_out") -> OutputGuardrail:
    """创建触发的 OutputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        return GuardrailResult(tripwire_triggered=True, message="blocked")
    return OutputGuardrail(name=name, guardrail_function=fn)


def _error_output_guardrail(name: str = "err_out") -> OutputGuardrail:
    """创建抛异常的 OutputGuardrail。"""
    async def fn(ctx: RunContext, text: str) -> GuardrailResult:
        raise RuntimeError("output guardrail boom")
    return OutputGuardrail(name=name, guardrail_function=fn)


# ─── Serial Input Guardrails ─────────────────────────────────────

class TestExecuteInputGuardrails:
    """_execute_input_guardrails 串行模式测试。"""

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        """全部通过不报错。"""
        await _execute_input_guardrails(
            [_safe_guardrail("g1"), _safe_guardrail("g2")],
            _ctx(), "hello",
        )

    @pytest.mark.asyncio
    async def test_tripwire_raises(self) -> None:
        """触发护栏抛出 InputGuardrailTripwireError。"""
        with pytest.raises(InputGuardrailTripwireError, match="blocked"):
            await _execute_input_guardrails(
                [_safe_guardrail(), _trip_guardrail()],
                _ctx(), "hello",
            )

    @pytest.mark.asyncio
    async def test_exception_raises_tripwire(self) -> None:
        """guardrail_function 抛异常 → 转为 InputGuardrailTripwireError（line 282）。"""
        with pytest.raises(InputGuardrailTripwireError, match="Guardrail execution error"):
            await _execute_input_guardrails(
                [_error_guardrail()], _ctx(), "hello",
            )

    @pytest.mark.asyncio
    async def test_condition_false_skips(self) -> None:
        """condition 返回 False → 跳过该护栏（lines 259-260）。"""
        g = _trip_guardrail(condition=lambda ctx: False)
        # 该护栏本应触发，但 condition=False 跳过
        await _execute_input_guardrails([g], _ctx(), "hello")

    @pytest.mark.asyncio
    async def test_condition_exception_treated_as_enabled(self) -> None:
        """condition 抛异常 → 当作启用（line 275）。"""
        def bad_condition(ctx: RunContext) -> bool:
            raise ValueError("condition error")

        g = _trip_guardrail(condition=bad_condition)
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails([g], _ctx(), "hello")

    @pytest.mark.asyncio
    async def test_serial_short_circuit(self) -> None:
        """串行模式：第一个触发后不执行后续护栏。"""
        call_count = 0
        original_trip = _trip_guardrail("trip")

        async def counting_fn(ctx: RunContext, text: str) -> GuardrailResult:
            nonlocal call_count
            call_count += 1
            return GuardrailResult(tripwire_triggered=False, message="ok")

        second = InputGuardrail(name="second", guardrail_function=counting_fn)
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails([original_trip, second], _ctx(), "hello")
        assert call_count == 0  # 第二个未执行

    @pytest.mark.asyncio
    async def test_with_tracing(self) -> None:
        """串行模式含 Tracing span 创建。"""
        config = RunConfig(tracing_enabled=True)
        tracing = _TracingCtx(config, "agent")
        await tracing.start_trace("wf")
        await tracing.start_agent_span("agent")

        await _execute_input_guardrails(
            [_safe_guardrail("g1")], _ctx(), "hello", tracing=tracing,
        )
        # 应该创建了一个 guardrail span
        guardrail_spans = [s for s in tracing.trace.spans if s.type.value == "guardrail"]
        assert len(guardrail_spans) == 1
        assert guardrail_spans[0].name == "g1"

    @pytest.mark.asyncio
    async def test_tracing_tripwire_span_failed(self) -> None:
        """触发护栏时 span 状态为 FAILED。"""
        config = RunConfig(tracing_enabled=True)
        tracing = _TracingCtx(config, "agent")
        await tracing.start_trace("wf")
        await tracing.start_agent_span("agent")

        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails(
                [_trip_guardrail()], _ctx(), "hello", tracing=tracing,
            )
        guardrail_spans = [s for s in tracing.trace.spans if s.type.value == "guardrail"]
        assert len(guardrail_spans) == 1
        assert guardrail_spans[0].status == SpanStatus.FAILED


# ─── Parallel Input Guardrails ──────────────────────────────────

class TestExecuteInputGuardrailsParallel:
    """_execute_input_guardrails_parallel 并行模式测试。"""

    @pytest.mark.asyncio
    async def test_all_pass_parallel(self) -> None:
        """并行全通过。"""
        await _execute_input_guardrails_parallel(
            [_safe_guardrail("g1"), _safe_guardrail("g2")],
            _ctx(), "hello",
        )

    @pytest.mark.asyncio
    async def test_tripwire_parallel(self) -> None:
        """并行模式：有触发项时抛出异常。"""
        with pytest.raises(InputGuardrailTripwireError, match="blocked"):
            await _execute_input_guardrails_parallel(
                [_safe_guardrail(), _trip_guardrail()],
                _ctx(), "hello",
            )

    @pytest.mark.asyncio
    async def test_exception_parallel(self) -> None:
        """并行模式：guardrail 异常转为 tripwire。"""
        with pytest.raises(InputGuardrailTripwireError, match="Guardrail execution error"):
            await _execute_input_guardrails_parallel(
                [_safe_guardrail(), _error_guardrail()],
                _ctx(), "hello",
            )

    @pytest.mark.asyncio
    async def test_condition_false_filtered(self) -> None:
        """并行模式：condition=False 的护栏在预过滤阶段排除。"""
        g = _trip_guardrail(condition=lambda ctx: False)
        # 只有一个被过滤的护栏 → 无活跃护栏 → 不触发
        await _execute_input_guardrails_parallel([g], _ctx(), "hello")

    @pytest.mark.asyncio
    async def test_condition_exception_included(self) -> None:
        """并行模式：condition 异常时当作启用。"""
        def bad_cond(ctx: RunContext) -> bool:
            raise ValueError("oops")

        g = _trip_guardrail(condition=bad_cond)
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails_parallel([g], _ctx(), "hello")

    @pytest.mark.asyncio
    async def test_dispatch_to_parallel(self) -> None:
        """_execute_input_guardrails parallel=True + >1 guardrail 调用并行版本。"""
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails(
                [_safe_guardrail(), _trip_guardrail()],
                _ctx(), "hello", parallel=True,
            )


# ─── Serial Output Guardrails ────────────────────────────────────

class TestExecuteOutputGuardrails:
    """_execute_output_guardrails 串行模式测试。"""

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        await _execute_output_guardrails(
            [_safe_output_guardrail()], _ctx(), "output",
        )

    @pytest.mark.asyncio
    async def test_tripwire_raises(self) -> None:
        with pytest.raises(OutputGuardrailTripwireError, match="blocked"):
            await _execute_output_guardrails(
                [_trip_output_guardrail()], _ctx(), "output",
            )

    @pytest.mark.asyncio
    async def test_exception_raises_tripwire(self) -> None:
        with pytest.raises(OutputGuardrailTripwireError, match="Guardrail execution error"):
            await _execute_output_guardrails(
                [_error_output_guardrail()], _ctx(), "output",
            )

    @pytest.mark.asyncio
    async def test_condition_false_skips(self) -> None:
        """condition 返回 False → 跳过。"""
        g = OutputGuardrail(
            name="skip",
            guardrail_function=AsyncMock(return_value=GuardrailResult(tripwire_triggered=True, message="trip")),
            condition=lambda ctx: False,
        )
        await _execute_output_guardrails([g], _ctx(), "output")

    @pytest.mark.asyncio
    async def test_condition_exception_treated_as_enabled(self) -> None:
        """condition 抛异常 → 当作启用。"""
        def bad_cond(ctx: RunContext) -> bool:
            raise ValueError("cond error")

        g = OutputGuardrail(
            name="err_cond",
            guardrail_function=AsyncMock(return_value=GuardrailResult(tripwire_triggered=True, message="trip")),
            condition=bad_cond,
        )
        with pytest.raises(OutputGuardrailTripwireError):
            await _execute_output_guardrails([g], _ctx(), "output")


# ─── Parallel Output Guardrails ──────────────────────────────────

class TestExecuteOutputGuardrailsParallel:
    """_execute_output_guardrails_parallel 并行模式测试。"""

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        await _execute_output_guardrails_parallel(
            [_safe_output_guardrail("a"), _safe_output_guardrail("b")],
            _ctx(), "output",
        )

    @pytest.mark.asyncio
    async def test_tripwire(self) -> None:
        with pytest.raises(OutputGuardrailTripwireError):
            await _execute_output_guardrails_parallel(
                [_safe_output_guardrail(), _trip_output_guardrail()],
                _ctx(), "output",
            )

    @pytest.mark.asyncio
    async def test_exception(self) -> None:
        with pytest.raises(OutputGuardrailTripwireError, match="Guardrail execution error"):
            await _execute_output_guardrails_parallel(
                [_safe_output_guardrail(), _error_output_guardrail()],
                _ctx(), "output",
            )

    @pytest.mark.asyncio
    async def test_all_filtered_noop(self) -> None:
        """所有护栏被 condition 过滤，无活跃护栏。"""
        g = OutputGuardrail(
            name="filtered",
            guardrail_function=AsyncMock(return_value=GuardrailResult(tripwire_triggered=True, message="trip")),
            condition=lambda ctx: False,
        )
        await _execute_output_guardrails_parallel([g], _ctx(), "output")

    @pytest.mark.asyncio
    async def test_dispatch_via_main(self) -> None:
        """通过 _execute_output_guardrails(parallel=True) 分派到并行版本。"""
        with pytest.raises(OutputGuardrailTripwireError):
            await _execute_output_guardrails(
                [_safe_output_guardrail(), _trip_output_guardrail()],
                _ctx(), "output", parallel=True,
            )
