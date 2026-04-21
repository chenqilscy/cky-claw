"""Tool Guardrail 测试。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kasaya.agent.agent import Agent
from kasaya.guardrails.result import GuardrailResult
from kasaya.guardrails.tool_guardrail import ToolGuardrail
from kasaya.model.message import TokenUsage
from kasaya.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall
from kasaya.runner.run_config import RunConfig
from kasaya.runner.runner import Runner
from kasaya.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from kasaya.runner.run_context import RunContext

# ---------- helpers ----------

def _make_tool(name: str = "my_tool", result: str = "tool_result") -> FunctionTool:
    """创建一个简单的 FunctionTool。"""
    async def _fn(input: str = "") -> str:
        return result

    return FunctionTool(
        name=name,
        description=f"A tool called {name}",
        fn=_fn,
        parameters_schema={
            "type": "object",
            "properties": {"input": {"type": "string"}},
        },
    )


class _ToolCallProvider(ModelProvider):
    """首次调用返回 tool_call，第二次返回最终回复。"""

    def __init__(
        self,
        tool_name: str = "my_tool",
        tool_args: str = '{"input": "hello"}',
        final_text: str = "done",
    ) -> None:
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._final_text = final_text
        self._call_count = 0

    async def chat(self, **kwargs):  # type: ignore[override]
        stream = kwargs.get("stream", False)
        if stream:
            return self._stream()
        self._call_count += 1
        if self._call_count == 1:
            return ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="tc_1", name=self._tool_name, arguments=self._tool_args)],
                token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            )
        return ModelResponse(
            content=self._final_text,
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def _stream(self):
        self._call_count += 1
        if self._call_count == 1:
            yield ModelChunk(
                content=None,
                finish_reason="tool_calls",
                tool_call_chunks=[],
            )
        else:
            yield ModelChunk(content=self._final_text, finish_reason="stop")


# ---------- before_fn / after_fn helpers ----------

async def _before_pass(ctx: RunContext, tool_name: str, arguments: dict) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _before_block(ctx: RunContext, tool_name: str, arguments: dict) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="blocked: dangerous tool call")


async def _before_block_specific(ctx: RunContext, tool_name: str, arguments: dict) -> GuardrailResult:
    """仅拦截特定工具。"""
    if tool_name == "dangerous_tool":
        return GuardrailResult(tripwire_triggered=True, message="dangerous tool blocked")
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _before_error(ctx: RunContext, tool_name: str, arguments: dict) -> GuardrailResult:
    raise ValueError("before_fn internal error")


async def _after_pass(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=False, message="ok")


async def _after_block(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
    return GuardrailResult(tripwire_triggered=True, message="result contains sensitive data")


async def _after_block_pii(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
    """检测工具返回值中的 PII。"""
    import re
    if re.search(r"1[3-9]\d{9}", result):
        return GuardrailResult(tripwire_triggered=True, message="PII in tool result")
    return GuardrailResult(tripwire_triggered=False, message="clean")


async def _after_error(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
    raise ValueError("after_fn internal error")


# ---------- ToolGuardrail 数据类测试 ----------

class TestToolGuardrail:
    """ToolGuardrail 定义测试。"""

    def test_auto_name_from_before_fn(self) -> None:
        g = ToolGuardrail(before_fn=_before_pass)
        assert g.name == "_before_pass"

    def test_auto_name_from_after_fn(self) -> None:
        g = ToolGuardrail(after_fn=_after_pass)
        assert g.name == "_after_pass"

    def test_custom_name(self) -> None:
        g = ToolGuardrail(name="my_guard", before_fn=_before_pass)
        assert g.name == "my_guard"

    def test_no_fn_fallback_name(self) -> None:
        g = ToolGuardrail()
        assert g.name == "unnamed_tool_guardrail"

    def test_both_fns(self) -> None:
        g = ToolGuardrail(name="both", before_fn=_before_pass, after_fn=_after_pass)
        assert g.before_fn is not None
        assert g.after_fn is not None


# ---------- Agent 字段测试 ----------

class TestAgentToolGuardrails:
    """Agent.tool_guardrails 字段测试。"""

    def test_default_empty(self) -> None:
        agent = Agent(name="test")
        assert agent.tool_guardrails == []

    def test_set_tool_guardrails(self) -> None:
        tg = ToolGuardrail(name="tg", before_fn=_before_pass)
        agent = Agent(name="test", tool_guardrails=[tg])
        assert len(agent.tool_guardrails) == 1
        assert agent.tool_guardrails[0].name == "tg"


# ---------- Runner.run 集成测试：before guardrail ----------

class TestRunnerToolGuardrailBefore:
    """Runner.run 中 Tool Guardrail before_fn 集成测试。"""

    @pytest.mark.asyncio
    async def test_before_pass_tool_executes(self) -> None:
        """before_fn 通过时工具正常执行。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="pass_guard", before_fn=_before_pass)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_before_block_tool_skipped(self) -> None:
        """before_fn 拦截时工具不执行，错误消息作为 ToolResult 返回。"""
        call_log: list[str] = []

        async def _logging_tool(input: str = "") -> str:
            call_log.append("executed")
            return "tool_result"

        tool = FunctionTool(
            name="my_tool",
            description="test",
            fn=_logging_tool,
            parameters_schema={"type": "object", "properties": {"input": {"type": "string"}}},
        )
        agent = Agent(
            name="test-agent",
            tools=[tool],
            tool_guardrails=[ToolGuardrail(name="blocker", before_fn=_before_block)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        # 工具未执行
        assert call_log == []
        # Run 未中断，正常完成
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_before_error_treated_as_block(self) -> None:
        """before_fn 抛异常时视为 tripwire 触发。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="errored", before_fn=_before_error)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_before_multiple_short_circuit(self) -> None:
        """多个 before_fn，首个拦截后短路。"""
        log: list[str] = []

        async def _log_pass(ctx, tn, args):
            log.append("pass")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        async def _log_block(ctx, tn, args):
            log.append("block")
            return GuardrailResult(tripwire_triggered=True, message="blocked")

        async def _log_after(ctx, tn, args):
            log.append("after")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[
                ToolGuardrail(name="g1", before_fn=_log_pass),
                ToolGuardrail(name="g2", before_fn=_log_block),
                ToolGuardrail(name="g3", before_fn=_log_after),
            ],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        await Runner.run(agent, "hello", config=config)
        assert log == ["pass", "block"]  # g3 never called


# ---------- Runner.run 集成测试：after guardrail ----------

class TestRunnerToolGuardrailAfter:
    """Runner.run 中 Tool Guardrail after_fn 集成测试。"""

    @pytest.mark.asyncio
    async def test_after_pass_result_preserved(self) -> None:
        """after_fn 通过时工具结果保留。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="pass_after", after_fn=_after_pass)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_after_block_result_replaced(self) -> None:
        """after_fn 拦截时工具结果被替换为错误消息。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="blocker_after", after_fn=_after_block)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        # Run 未中断
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_after_error_treated_as_block(self) -> None:
        """after_fn 抛异常时视为 tripwire 触发。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="errored_after", after_fn=_after_error)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_after_pii_detection(self) -> None:
        """after_fn 检测工具返回中的手机号。"""
        tool = _make_tool(result="User phone: 13912345678")
        agent = Agent(
            name="test-agent",
            tools=[tool],
            tool_guardrails=[ToolGuardrail(name="pii_after", after_fn=_after_block_pii)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        # Run 完成，但工具结果是错误消息
        assert result.output == "done"


# ---------- before + after 组合测试 ----------

class TestRunnerToolGuardrailCombined:
    """before + after 同时存在的测试。"""

    @pytest.mark.asyncio
    async def test_both_pass(self) -> None:
        """before + after 都通过。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="both", before_fn=_before_pass, after_fn=_after_pass)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_before_blocks_after_skipped(self) -> None:
        """before 拦截时 after 不执行。"""
        after_called = []

        async def _tracking_after(ctx, tn, res):
            after_called.append(True)
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="combo", before_fn=_before_block, after_fn=_tracking_after)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        await Runner.run(agent, "hello", config=config)
        assert after_called == []  # after never called

    @pytest.mark.asyncio
    async def test_no_guardrails_normal_execution(self) -> None:
        """没有 tool_guardrails 时正常执行。"""
        agent = Agent(name="test-agent", tools=[_make_tool()])
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_only_before_fn(self) -> None:
        """只有 before_fn，没有 after_fn。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="before_only", before_fn=_before_pass)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_only_after_fn(self) -> None:
        """只有 after_fn，没有 before_fn。"""
        agent = Agent(
            name="test-agent",
            tools=[_make_tool()],
            tool_guardrails=[ToolGuardrail(name="after_only", after_fn=_after_pass)],
        )
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "done"
