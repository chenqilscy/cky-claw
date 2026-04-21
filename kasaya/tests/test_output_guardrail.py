"""Output Guardrail 测试。"""

from __future__ import annotations

import pytest

from kasaya.agent.agent import Agent
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.regex_guardrail import RegexGuardrail
from kasaya.guardrails.result import GuardrailResult, OutputGuardrailTripwireError
from kasaya.model.message import TokenUsage
from kasaya.model.provider import ModelChunk, ModelProvider, ModelResponse
from kasaya.runner.run_config import RunConfig
from kasaya.runner.run_context import RunContext
from kasaya.runner.runner import Runner, _execute_output_guardrails

# ---------- helpers ----------

class _MockProvider(ModelProvider):
    """固定返回文本的 Mock Provider。"""

    def __init__(self, text: str = "ok") -> None:
        self._text = text

    async def chat(self, **kwargs):  # type: ignore[override]
        stream = kwargs.get("stream", False)
        if stream:
            return self._stream()
        return ModelResponse(
            content=self._text,
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def _stream(self):
        yield ModelChunk(content=self._text, finish_reason="stop")


async def _pass_guardrail(ctx: RunContext, output_text: str) -> GuardrailResult:
    """始终通过的 output guardrail。"""
    return GuardrailResult(tripwire_triggered=False, message="safe")


async def _block_guardrail(ctx: RunContext, output_text: str) -> GuardrailResult:
    """始终拦截的 output guardrail。"""
    return GuardrailResult(tripwire_triggered=True, message="blocked: sensitive data detected")


async def _phone_guardrail(ctx: RunContext, output_text: str) -> GuardrailResult:
    """检测手机号的 output guardrail。"""
    import re
    if re.search(r"1[3-9]\d{9}", output_text):
        return GuardrailResult(tripwire_triggered=True, message="PII detected: phone number")
    return GuardrailResult(tripwire_triggered=False, message="clean")


async def _error_guardrail(ctx: RunContext, output_text: str) -> GuardrailResult:
    """抛出异常的 output guardrail。"""
    raise ValueError("guardrail internal error")


# ---------- OutputGuardrail 数据类测试 ----------

class TestOutputGuardrail:
    """OutputGuardrail 定义测试。"""

    def test_auto_name_from_function(self) -> None:
        g = OutputGuardrail(guardrail_function=_pass_guardrail)
        assert g.name == "_pass_guardrail"

    def test_custom_name(self) -> None:
        g = OutputGuardrail(guardrail_function=_pass_guardrail, name="my_output_guard")
        assert g.name == "my_output_guard"

    def test_lambda_name_fallback(self) -> None:
        g = OutputGuardrail(guardrail_function=lambda ctx, text: GuardrailResult())
        assert g.name == "<lambda>"


# ---------- OutputGuardrailTripwireError 测试 ----------

class TestOutputGuardrailTripwireError:
    """TripwireError 异常测试。"""

    def test_error_attributes(self) -> None:
        err = OutputGuardrailTripwireError("out_guard", "sensitive output")
        assert err.guardrail_name == "out_guard"
        assert err.message == "sensitive output"
        assert "out_guard" in str(err)
        assert "sensitive output" in str(err)

    def test_is_exception(self) -> None:
        assert issubclass(OutputGuardrailTripwireError, Exception)


# ---------- _execute_output_guardrails 测试 ----------

class TestExecuteOutputGuardrails:
    """_execute_output_guardrails 内部函数测试。"""

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        """所有 output guardrails 通过时不抛异常。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        await _execute_output_guardrails(
            [OutputGuardrail(guardrail_function=_pass_guardrail)],
            ctx,
            "hello world",
        )

    @pytest.mark.asyncio
    async def test_tripwire_triggered(self) -> None:
        """触发 tripwire 时抛出 OutputGuardrailTripwireError。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(OutputGuardrailTripwireError) as exc_info:
            await _execute_output_guardrails(
                [OutputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
                ctx,
                "some output",
            )
        assert exc_info.value.guardrail_name == "blocker"
        assert "sensitive data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_short_circuit(self) -> None:
        """首个触发后短路，后续 guardrails 不执行。"""
        call_log: list[str] = []

        async def _log_pass(ctx: RunContext, text: str) -> GuardrailResult:
            call_log.append("pass")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        async def _log_block(ctx: RunContext, text: str) -> GuardrailResult:
            call_log.append("block")
            return GuardrailResult(tripwire_triggered=True, message="blocked")

        async def _log_after(ctx: RunContext, text: str) -> GuardrailResult:
            call_log.append("after")
            return GuardrailResult(tripwire_triggered=False, message="ok")

        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(OutputGuardrailTripwireError):
            await _execute_output_guardrails(
                [
                    OutputGuardrail(guardrail_function=_log_pass, name="pass"),
                    OutputGuardrail(guardrail_function=_log_block, name="block"),
                    OutputGuardrail(guardrail_function=_log_after, name="after"),
                ],
                ctx,
                "some output",
            )
        assert call_log == ["pass", "block"]  # "after" 未执行

    @pytest.mark.asyncio
    async def test_guardrail_exception_wraps_as_tripwire(self) -> None:
        """guardrail 执行异常时包装为 TripwireError。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(OutputGuardrailTripwireError) as exc_info:
            await _execute_output_guardrails(
                [OutputGuardrail(guardrail_function=_error_guardrail, name="errored")],
                ctx,
                "some output",
            )
        assert exc_info.value.guardrail_name == "errored"
        assert "execution error" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_phone_guardrail_pass(self) -> None:
        """手机号检测 — 正常输出通过。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        await _execute_output_guardrails(
            [OutputGuardrail(guardrail_function=_phone_guardrail, name="phone_check")],
            ctx,
            "Here is the info you requested.",
        )

    @pytest.mark.asyncio
    async def test_phone_guardrail_block(self) -> None:
        """手机号检测 — 包含手机号被拦截。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(OutputGuardrailTripwireError) as exc_info:
            await _execute_output_guardrails(
                [OutputGuardrail(guardrail_function=_phone_guardrail, name="phone_check")],
                ctx,
                "Your phone number is 13912345678",
            )
        assert exc_info.value.guardrail_name == "phone_check"
        assert "PII" in exc_info.value.message


# ---------- RegexGuardrail.as_output_fn 测试 ----------

class TestRegexGuardrailAsOutputFn:
    """RegexGuardrail 的 as_output_fn 方法测试。"""

    @pytest.mark.asyncio
    async def test_as_output_fn_pass(self) -> None:
        """正则不匹配时通过。"""
        rg = RegexGuardrail(patterns=[r"1[3-9]\d{9}"], message="手机号泄露", name="phone_regex")
        fn = rg.as_output_fn()
        result = await fn(None, "Hello world")
        assert result.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_as_output_fn_block(self) -> None:
        """正则匹配时拦截。"""
        rg = RegexGuardrail(patterns=[r"1[3-9]\d{9}"], message="手机号泄露", name="phone_regex")
        fn = rg.as_output_fn()
        result = await fn(None, "Call me at 13912345678")
        assert result.tripwire_triggered is True
        assert result.message == "手机号泄露"


# ---------- Agent 字段测试 ----------

class TestAgentOutputGuardrails:
    """Agent.output_guardrails 字段测试。"""

    def test_default_empty(self) -> None:
        agent = Agent(name="test")
        assert agent.output_guardrails == []

    def test_set_output_guardrails(self) -> None:
        g = OutputGuardrail(guardrail_function=_pass_guardrail, name="out_check")
        agent = Agent(name="test", output_guardrails=[g])
        assert len(agent.output_guardrails) == 1
        assert agent.output_guardrails[0].name == "out_check"


# ---------- Runner.run 集成测试 ----------

class TestRunnerOutputGuardrail:
    """Runner.run 中 Output Guardrail 执行的集成测试。"""

    @pytest.mark.asyncio
    async def test_run_passes_when_output_clean(self) -> None:
        """输出安全时正常返回 RunResult。"""
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=_pass_guardrail, name="safe")],
        )
        config = RunConfig(model_provider=_MockProvider("clean output"))
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "clean output"

    @pytest.mark.asyncio
    async def test_run_blocked_when_output_triggers(self) -> None:
        """输出触发 guardrail 时抛出 OutputGuardrailTripwireError。"""
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
        )
        config = RunConfig(model_provider=_MockProvider("sensitive data"))
        with pytest.raises(OutputGuardrailTripwireError) as exc_info:
            await Runner.run(agent, "hello", config=config)
        assert exc_info.value.guardrail_name == "blocker"

    @pytest.mark.asyncio
    async def test_run_with_regex_output_guardrail(self) -> None:
        """使用 RegexGuardrail 检测输出中的手机号。"""
        rg = RegexGuardrail(patterns=[r"1[3-9]\d{9}"], message="手机号泄露", name="phone_check")
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=rg.as_output_fn(), name="phone_check")],
        )
        config = RunConfig(model_provider=_MockProvider("Your number is 13912345678"))
        with pytest.raises(OutputGuardrailTripwireError) as exc_info:
            await Runner.run(agent, "show me the number", config=config)
        assert "手机号泄露" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_run_regex_output_passes(self) -> None:
        """RegexGuardrail 输出不匹配时正常返回。"""
        rg = RegexGuardrail(patterns=[r"1[3-9]\d{9}"], message="手机号泄露", name="phone_check")
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=rg.as_output_fn(), name="phone_check")],
        )
        config = RunConfig(model_provider=_MockProvider("Here is the answer: 42."))
        result = await Runner.run(agent, "what is the answer?", config=config)
        assert result.output == "Here is the answer: 42."

    @pytest.mark.asyncio
    async def test_run_no_output_guardrails(self) -> None:
        """没有 output guardrails 时正常返回。"""
        agent = Agent(name="test-agent")
        config = RunConfig(model_provider=_MockProvider("plain answer"))
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "plain answer"

    @pytest.mark.asyncio
    async def test_both_input_and_output_guardrails(self) -> None:
        """Input + Output guardrails 共存：输入通过、输出拦截。"""
        from kasaya.guardrails.input_guardrail import InputGuardrail

        async def _input_pass(ctx, text):
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test-agent",
            input_guardrails=[InputGuardrail(guardrail_function=_input_pass, name="in_pass")],
            output_guardrails=[OutputGuardrail(guardrail_function=_block_guardrail, name="out_block")],
        )
        config = RunConfig(model_provider=_MockProvider("bad output"))
        with pytest.raises(OutputGuardrailTripwireError):
            await Runner.run(agent, "hello", config=config)


# ---------- Runner.run_streamed 集成测试 ----------

class TestRunnerStreamedOutputGuardrail:
    """Runner.run_streamed 中 Output Guardrail 执行的集成测试。"""

    @pytest.mark.asyncio
    async def test_streamed_passes_when_output_clean(self) -> None:
        """流式：输出安全时正常完成。"""
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=_pass_guardrail, name="safe")],
        )
        config = RunConfig(model_provider=_MockProvider("clean output"))
        events = []
        async for event in Runner.run_streamed(agent, "hello", config=config):
            events.append(event)
        # 应有 RUN_COMPLETE 事件
        assert any(e.type.value == "run_complete" for e in events)

    @pytest.mark.asyncio
    async def test_streamed_blocked_when_output_triggers(self) -> None:
        """流式：输出触发 guardrail 时抛出异常。"""
        agent = Agent(
            name="test-agent",
            output_guardrails=[OutputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
        )
        config = RunConfig(model_provider=_MockProvider("sensitive data"))
        with pytest.raises(OutputGuardrailTripwireError):
            async for _ in Runner.run_streamed(agent, "hello", config=config):
                pass
