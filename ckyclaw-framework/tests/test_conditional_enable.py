"""条件启用测试 — Guardrail condition 字段动态跳过。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult
from ckyclaw_framework.runner.runner import _execute_input_guardrails, _execute_output_guardrails
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.run_config import RunConfig


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _always_block(_ctx, _text) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="blocked")


async def _always_pass(_ctx, _text) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


def _make_context(**extra_ctx: object) -> RunContext:
    agent = Agent(name="test", instructions="hi")
    ctx = {"env": "production"}
    ctx.update(extra_ctx)
    return RunContext(agent=agent, config=RunConfig(), context=ctx)


# ---------------------------------------------------------------------------
# InputGuardrail condition
# ---------------------------------------------------------------------------


class TestInputGuardrailCondition:
    """InputGuardrail condition 字段测试。"""

    @pytest.mark.asyncio
    async def test_no_condition_executes_normally(self):
        """无 condition 时正常执行。"""
        g = InputGuardrail(guardrail_function=_always_pass, name="no-condition")
        assert g.condition is None
        ctx = _make_context()
        # 不抛异常 = 通过
        await _execute_input_guardrails([g], ctx, "test input")

    @pytest.mark.asyncio
    async def test_condition_true_executes(self):
        """condition 返回 True 时执行 guardrail。"""
        from ckyclaw_framework.guardrails.result import InputGuardrailTripwireError

        g = InputGuardrail(
            guardrail_function=_always_block,
            name="cond-true",
            condition=lambda ctx: True,
        )
        ctx = _make_context()
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails([g], ctx, "test input")

    @pytest.mark.asyncio
    async def test_condition_false_skips(self):
        """condition 返回 False 时跳过 guardrail。"""
        g = InputGuardrail(
            guardrail_function=_always_block,
            name="cond-false",
            condition=lambda ctx: False,
        )
        ctx = _make_context()
        # 不抛异常 = 跳过了
        await _execute_input_guardrails([g], ctx, "test input")

    @pytest.mark.asyncio
    async def test_condition_based_on_context(self):
        """condition 基于 RunContext.context 动态判断。"""
        g = InputGuardrail(
            guardrail_function=_always_block,
            name="env-check",
            condition=lambda ctx: ctx.context.get("env") == "staging",
        )
        ctx = _make_context()  # env=production
        # staging 条件不满足，应跳过
        await _execute_input_guardrails([g], ctx, "test input")

    @pytest.mark.asyncio
    async def test_mixed_conditions(self):
        """混合有无 condition 的 guardrail。"""
        from ckyclaw_framework.guardrails.result import InputGuardrailTripwireError

        call_log = []

        async def _logging_pass(_ctx, _text):
            call_log.append("pass")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        async def _logging_block(_ctx, _text):
            call_log.append("block")
            return GuardrailResult(tripwire_triggered=True, message="no")

        g1 = InputGuardrail(guardrail_function=_logging_pass, name="always-on")
        g2 = InputGuardrail(
            guardrail_function=_logging_block,
            name="skip-me",
            condition=lambda ctx: False,
        )
        g3 = InputGuardrail(guardrail_function=_logging_pass, name="also-on")

        ctx = _make_context()
        await _execute_input_guardrails([g1, g2, g3], ctx, "test")
        # g2 被跳过，只有 g1 和 g3 执行
        assert call_log == ["pass", "pass"]


# ---------------------------------------------------------------------------
# OutputGuardrail condition
# ---------------------------------------------------------------------------


class TestOutputGuardrailCondition:
    """OutputGuardrail condition 字段测试。"""

    @pytest.mark.asyncio
    async def test_condition_false_skips_output(self):
        """condition 返回 False 时跳过 output guardrail。"""
        g = OutputGuardrail(
            guardrail_function=_always_block,
            name="skip-output",
            condition=lambda ctx: False,
        )
        ctx = _make_context()
        await _execute_output_guardrails([g], ctx, "output text")


# ---------------------------------------------------------------------------
# ToolGuardrail condition
# ---------------------------------------------------------------------------


class TestToolGuardrailCondition:
    """ToolGuardrail condition 字段测试。"""

    def test_condition_field_exists(self):
        """ToolGuardrail 支持 condition 字段。"""
        g = ToolGuardrail(
            name="conditional-tool-guard",
            condition=lambda ctx: ctx.context.get("strict", False),
        )
        assert g.condition is not None

    def test_condition_default_none(self):
        """默认 condition 为 None。"""
        g = ToolGuardrail(name="default")
        assert g.condition is None
