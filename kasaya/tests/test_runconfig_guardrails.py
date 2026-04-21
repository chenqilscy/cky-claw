"""RunConfig 级 Guardrail 追加测试。

验证 RunConfig.input_guardrails / output_guardrails / tool_guardrails
追加到 Agent 级 guardrails 之后执行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kasaya.agent.agent import Agent
from kasaya.guardrails.input_guardrail import InputGuardrail
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from kasaya.guardrails.tool_guardrail import ToolGuardrail
from kasaya.model.message import TokenUsage
from kasaya.model.provider import ModelProvider, ModelResponse, ToolCall
from kasaya.runner.run_config import RunConfig
from kasaya.runner.runner import Runner
from kasaya.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from kasaya.runner.run_context import RunContext

# ---------- helpers ----------

class _TextProvider(ModelProvider):
    """固定返回文本。"""

    def __init__(self, text: str = "hello") -> None:
        self._text = text

    async def chat(self, **kwargs):
        return ModelResponse(
            content=self._text,
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )


class _ToolCallProvider(ModelProvider):
    """首次返回 tool_call，第二次返回文本。"""

    def __init__(self, final_text: str = "done") -> None:
        self._final_text = final_text
        self._call_count = 0

    async def chat(self, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            return ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="tc_1", name="my_tool", arguments='{"input": "hi"}')],
                token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            )
        return ModelResponse(
            content=self._final_text,
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )


def _make_tool(name: str = "my_tool", result: str = "tool_ok") -> FunctionTool:
    async def _fn(input: str = "") -> str:
        return result

    return FunctionTool(
        name=name,
        description=f"tool {name}",
        fn=_fn,
        parameters_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    )


# guardrail helpers
async def _input_pass(ctx: RunContext, text: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _input_block(ctx: RunContext, text: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="runconfig input blocked")


async def _output_pass(ctx: RunContext, text: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _output_block(ctx: RunContext, text: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="runconfig output blocked")


async def _tool_before_pass(ctx: RunContext, tool_name: str, args: dict) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _tool_before_block(ctx: RunContext, tool_name: str, args: dict) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="runconfig tool before blocked")


async def _tool_after_block(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="runconfig tool after blocked")


# ═══════════════════════════════════════════════════════════════════
# RunConfig.input_guardrails 追加测试
# ═══════════════════════════════════════════════════════════════════

class TestRunConfigInputGuardrails:
    """RunConfig 级 InputGuardrail 测试。"""

    @pytest.mark.asyncio
    async def test_runconfig_input_guardrail_blocks(self) -> None:
        """Agent 无 guardrail，RunConfig 追加的 InputGuardrail 拦截。"""
        agent = Agent(name="test")
        config = RunConfig(
            model_provider=_TextProvider(),
            input_guardrails=[InputGuardrail(guardrail_function=_input_block, name="rc_block")],
        )
        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)

    @pytest.mark.asyncio
    async def test_runconfig_input_guardrail_pass(self) -> None:
        """RunConfig 追加的 InputGuardrail 通过时正常。"""
        agent = Agent(name="test")
        config = RunConfig(
            model_provider=_TextProvider("ok"),
            input_guardrails=[InputGuardrail(guardrail_function=_input_pass, name="rc_pass")],
        )
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "ok"

    @pytest.mark.asyncio
    async def test_agent_pass_runconfig_blocks(self) -> None:
        """Agent 级通过 + RunConfig 级拦截 → 拦截（RunConfig 追加在后面）。"""
        agent = Agent(
            name="test",
            input_guardrails=[InputGuardrail(guardrail_function=_input_pass, name="agent_pass")],
        )
        config = RunConfig(
            model_provider=_TextProvider(),
            input_guardrails=[InputGuardrail(guardrail_function=_input_block, name="rc_block")],
        )
        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)

    @pytest.mark.asyncio
    async def test_agent_blocks_runconfig_not_reached(self) -> None:
        """Agent 级拦截 → 短路，RunConfig 级不执行。"""
        rc_called = []

        async def _tracking_rc(ctx, text):
            rc_called.append(True)
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test",
            input_guardrails=[InputGuardrail(guardrail_function=_input_block, name="agent_block")],
        )
        config = RunConfig(
            model_provider=_TextProvider(),
            input_guardrails=[InputGuardrail(guardrail_function=_tracking_rc, name="rc_tracking")],
        )
        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)
        assert rc_called == []  # 短路，RunConfig 级未执行

    @pytest.mark.asyncio
    async def test_execution_order(self) -> None:
        """Agent 级先执行，RunConfig 级后执行。"""
        order: list[str] = []

        async def _agent_fn(ctx, text):
            order.append("agent")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        async def _rc_fn(ctx, text):
            order.append("runconfig")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test",
            input_guardrails=[InputGuardrail(guardrail_function=_agent_fn, name="agent_g")],
        )
        config = RunConfig(
            model_provider=_TextProvider("ok"),
            input_guardrails=[InputGuardrail(guardrail_function=_rc_fn, name="rc_g")],
        )
        await Runner.run(agent, "hello", config=config)
        assert order == ["agent", "runconfig"]


# ═══════════════════════════════════════════════════════════════════
# RunConfig.output_guardrails 追加测试
# ═══════════════════════════════════════════════════════════════════

class TestRunConfigOutputGuardrails:
    """RunConfig 级 OutputGuardrail 测试。"""

    @pytest.mark.asyncio
    async def test_runconfig_output_guardrail_blocks(self) -> None:
        """Agent 无 guardrail，RunConfig 追加的 OutputGuardrail 拦截。"""
        agent = Agent(name="test")
        config = RunConfig(
            model_provider=_TextProvider("sensitive data"),
            output_guardrails=[OutputGuardrail(guardrail_function=_output_block, name="rc_out_block")],
        )
        with pytest.raises(OutputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)

    @pytest.mark.asyncio
    async def test_runconfig_output_guardrail_pass(self) -> None:
        """RunConfig 追加的 OutputGuardrail 通过时正常。"""
        agent = Agent(name="test")
        config = RunConfig(
            model_provider=_TextProvider("ok"),
            output_guardrails=[OutputGuardrail(guardrail_function=_output_pass, name="rc_out_pass")],
        )
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "ok"

    @pytest.mark.asyncio
    async def test_agent_pass_runconfig_output_blocks(self) -> None:
        """Agent 级通过 + RunConfig 级拦截 → 拦截。"""
        agent = Agent(
            name="test",
            output_guardrails=[OutputGuardrail(guardrail_function=_output_pass, name="agent_out_pass")],
        )
        config = RunConfig(
            model_provider=_TextProvider("secret"),
            output_guardrails=[OutputGuardrail(guardrail_function=_output_block, name="rc_out_block")],
        )
        with pytest.raises(OutputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)


# ═══════════════════════════════════════════════════════════════════
# RunConfig.tool_guardrails 追加测试
# ═══════════════════════════════════════════════════════════════════

class TestRunConfigToolGuardrails:
    """RunConfig 级 ToolGuardrail 测试。"""

    @pytest.mark.asyncio
    async def test_runconfig_tool_before_blocks(self) -> None:
        """Agent 无 tool_guardrails，RunConfig 追加的 before_fn 拦截。"""
        call_log: list[str] = []

        async def _logging_tool(input: str = "") -> str:
            call_log.append("executed")
            return "tool_ok"

        tool = FunctionTool(
            name="my_tool", description="test", fn=_logging_tool,
            parameters_schema={"type": "object", "properties": {"input": {"type": "string"}}},
        )
        agent = Agent(name="test", tools=[tool])
        config = RunConfig(
            model_provider=_ToolCallProvider(),
            tool_guardrails=[ToolGuardrail(name="rc_tg_block", before_fn=_tool_before_block)],
        )
        result = await Runner.run(agent, "hello", config=config)
        assert call_log == []  # 工具未执行
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_runconfig_tool_after_blocks(self) -> None:
        """RunConfig 追加的 after_fn 拦截工具结果。"""
        agent = Agent(name="test", tools=[_make_tool()])
        config = RunConfig(
            model_provider=_ToolCallProvider(),
            tool_guardrails=[ToolGuardrail(name="rc_tg_after", after_fn=_tool_after_block)],
        )
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_agent_tool_pass_runconfig_blocks(self) -> None:
        """Agent 级 tool guardrail 通过 + RunConfig 级拦截。"""
        agent = Agent(
            name="test",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="agent_tg", before_fn=_tool_before_pass)],
        )
        config = RunConfig(
            model_provider=_ToolCallProvider(),
            tool_guardrails=[ToolGuardrail(name="rc_tg", before_fn=_tool_before_block)],
        )
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_empty_runconfig_guardrails(self) -> None:
        """RunConfig guardrails 为空时不影响执行。"""
        agent = Agent(name="test")
        config = RunConfig(model_provider=_TextProvider("ok"))
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "ok"
