"""条件启用测试 — Guardrail condition 字段动态跳过。"""

from __future__ import annotations

import pytest

from kasaya.agent.agent import Agent
from kasaya.guardrails.input_guardrail import InputGuardrail
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.result import GuardrailResult
from kasaya.guardrails.tool_guardrail import ToolGuardrail
from kasaya.runner.run_config import RunConfig
from kasaya.runner.run_context import RunContext
from kasaya.runner.runner import _build_tool_schemas, _execute_input_guardrails, _execute_output_guardrails
from kasaya.tools.function_tool import FunctionTool

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
        from kasaya.guardrails.result import InputGuardrailTripwireError

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


# ---------------------------------------------------------------------------
# FunctionTool condition
# ---------------------------------------------------------------------------


class TestFunctionToolCondition:
    """FunctionTool condition 字段测试。"""

    def test_condition_default_none(self):
        """默认 condition 为 None（始终启用）。"""
        tool = FunctionTool(name="always-on", description="desc")
        assert tool.condition is None

    def test_condition_field_accepts_callable(self):
        """condition 接受 Callable。"""
        tool = FunctionTool(
            name="cond-tool",
            description="desc",
            condition=lambda ctx: ctx.context.get("enable_tool", False),
        )
        assert tool.condition is not None

    def test_condition_true_includes_in_schemas(self):
        """condition 返回 True 时工具包含在 schemas 中。"""
        tool = FunctionTool(
            name="included",
            description="desc",
            condition=lambda ctx: True,
        )
        agent = Agent(name="test", tools=[tool])
        ctx = _make_context()
        schemas = _build_tool_schemas(agent, ctx)
        names = [s["function"]["name"] for s in schemas]
        assert "included" in names

    def test_condition_false_excludes_from_schemas(self):
        """condition 返回 False 时工具排除在 schemas 外。"""
        tool = FunctionTool(
            name="excluded",
            description="desc",
            condition=lambda ctx: False,
        )
        agent = Agent(name="test", tools=[tool])
        ctx = _make_context()
        schemas = _build_tool_schemas(agent, ctx)
        names = [s["function"]["name"] for s in schemas]
        assert "excluded" not in names

    def test_no_condition_always_included(self):
        """无 condition 时始终包含。"""
        tool = FunctionTool(name="always", description="desc")
        agent = Agent(name="test", tools=[tool])
        ctx = _make_context()
        schemas = _build_tool_schemas(agent, ctx)
        assert len(schemas) == 1

    def test_condition_based_on_context(self):
        """condition 可根据 RunContext.context 动态决定。"""
        tool = FunctionTool(
            name="dynamic",
            description="desc",
            condition=lambda ctx: ctx.context.get("premium", False),
        )
        agent = Agent(name="test", tools=[tool])

        ctx_disabled = _make_context(premium=False)
        assert len(_build_tool_schemas(agent, ctx_disabled)) == 0

        ctx_enabled = _make_context(premium=True)
        assert len(_build_tool_schemas(agent, ctx_enabled)) == 1

    def test_mixed_tools_condition(self):
        """混合有无 condition 的工具。"""
        tool_always = FunctionTool(name="always", description="always on")
        tool_cond_on = FunctionTool(name="cond-on", description="on", condition=lambda ctx: True)
        tool_cond_off = FunctionTool(name="cond-off", description="off", condition=lambda ctx: False)

        agent = Agent(name="test", tools=[tool_always, tool_cond_on, tool_cond_off])
        ctx = _make_context()
        schemas = _build_tool_schemas(agent, ctx)
        names = [s["function"]["name"] for s in schemas]
        assert "always" in names
        assert "cond-on" in names
        assert "cond-off" not in names

    def test_build_tool_schemas_without_context(self):
        """run_ctx 为 None 时，所有工具均包含（向后兼容）。"""
        tool = FunctionTool(name="cond", description="desc", condition=lambda ctx: False)
        agent = Agent(name="test", tools=[tool])
        schemas = _build_tool_schemas(agent, None)
        assert len(schemas) == 1  # condition 不检查


# ---------------------------------------------------------------------------
# Agent-as-Tool condition
# ---------------------------------------------------------------------------


class TestAgentAsToolCondition:
    """Agent.as_tool() condition 参数测试。"""

    def test_as_tool_no_condition(self):
        """默认无 condition。"""
        agent = Agent(name="sub", description="sub agent")
        tool = agent.as_tool()
        assert tool.condition is None

    def test_as_tool_with_condition(self):
        """as_tool 传入 condition。"""
        agent = Agent(name="sub", description="sub agent")
        def cond(ctx):
            return ctx.context.get("use_sub", False)
        tool = agent.as_tool(condition=cond)
        assert tool.condition is cond

    def test_as_tool_condition_filters_in_schemas(self):
        """as_tool condition 在 _build_tool_schemas 中生效。"""
        sub_agent = Agent(name="sub", description="helper")
        tool = sub_agent.as_tool(condition=lambda ctx: False)

        manager = Agent(name="manager", tools=[tool])
        ctx = _make_context()
        schemas = _build_tool_schemas(manager, ctx)
        assert len(schemas) == 0

    def test_as_tool_condition_true_includes(self):
        """as_tool condition 返回 True 时工具可用。"""
        sub_agent = Agent(name="sub", description="helper")
        tool = sub_agent.as_tool(condition=lambda ctx: True)

        manager = Agent(name="manager", tools=[tool])
        ctx = _make_context()
        schemas = _build_tool_schemas(manager, ctx)
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "sub"
