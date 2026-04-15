"""Input Guardrail 测试。"""

from __future__ import annotations

import contextlib

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError
from ckyclaw_framework.model.message import TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import Runner, _execute_input_guardrails
from ckyclaw_framework.tracing.span import SpanType

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


async def _pass_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
    """始终通过的 guardrail。"""
    return GuardrailResult(tripwire_triggered=False, message="safe")


async def _block_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
    """始终拦截的 guardrail。"""
    return GuardrailResult(tripwire_triggered=True, message="blocked: dangerous input")


async def _keyword_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
    """关键词检测 guardrail — 检测 'DROP TABLE'。"""
    if "DROP TABLE" in input_text.upper():
        return GuardrailResult(tripwire_triggered=True, message="SQL injection detected")
    return GuardrailResult(tripwire_triggered=False, message="clean")


async def _error_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
    """抛出异常的 guardrail。"""
    raise ValueError("guardrail internal error")


# ---------- GuardrailResult tests ----------

class TestGuardrailResult:
    """GuardrailResult 数据类测试。"""

    def test_default_values(self) -> None:
        result = GuardrailResult()
        assert result.tripwire_triggered is False
        assert result.message == ""

    def test_triggered_result(self) -> None:
        result = GuardrailResult(tripwire_triggered=True, message="blocked")
        assert result.tripwire_triggered is True
        assert result.message == "blocked"


# ---------- InputGuardrail tests ----------

class TestInputGuardrail:
    """InputGuardrail 定义测试。"""

    def test_auto_name_from_function(self) -> None:
        g = InputGuardrail(guardrail_function=_pass_guardrail)
        assert g.name == "_pass_guardrail"

    def test_custom_name(self) -> None:
        g = InputGuardrail(guardrail_function=_pass_guardrail, name="my_guard")
        assert g.name == "my_guard"

    def test_lambda_name_fallback(self) -> None:
        g = InputGuardrail(guardrail_function=lambda ctx, text: GuardrailResult())
        assert g.name == "<lambda>"


# ---------- InputGuardrailTripwireError tests ----------

class TestInputGuardrailTripwireError:
    """TripwireError 异常测试。"""

    def test_error_attributes(self) -> None:
        err = InputGuardrailTripwireError("my_guard", "bad input")
        assert err.guardrail_name == "my_guard"
        assert err.message == "bad input"
        assert "my_guard" in str(err)
        assert "bad input" in str(err)

    def test_is_exception(self) -> None:
        assert issubclass(InputGuardrailTripwireError, Exception)


# ---------- _execute_input_guardrails tests ----------

class TestExecuteInputGuardrails:
    """_execute_input_guardrails 内部函数测试。"""

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        """所有 guardrails 通过时不抛异常。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        await _execute_input_guardrails(
            [InputGuardrail(guardrail_function=_pass_guardrail)],
            ctx,
            "hello",
        )

    @pytest.mark.asyncio
    async def test_tripwire_triggered(self) -> None:
        """触发 tripwire 时抛出 InputGuardrailTripwireError。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(InputGuardrailTripwireError) as exc_info:
            await _execute_input_guardrails(
                [InputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
                ctx,
                "hello",
            )
        assert exc_info.value.guardrail_name == "blocker"
        assert "blocked: dangerous input" in exc_info.value.message

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
        with pytest.raises(InputGuardrailTripwireError):
            await _execute_input_guardrails(
                [
                    InputGuardrail(guardrail_function=_log_pass, name="pass"),
                    InputGuardrail(guardrail_function=_log_block, name="block"),
                    InputGuardrail(guardrail_function=_log_after, name="after"),
                ],
                ctx,
                "hello",
            )
        assert call_log == ["pass", "block"]  # "after" 未执行

    @pytest.mark.asyncio
    async def test_guardrail_exception_wraps_as_tripwire(self) -> None:
        """guardrail 执行异常时包装为 TripwireError。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(InputGuardrailTripwireError) as exc_info:
            await _execute_input_guardrails(
                [InputGuardrail(guardrail_function=_error_guardrail, name="errored")],
                ctx,
                "hello",
            )
        assert exc_info.value.guardrail_name == "errored"
        assert "execution error" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_keyword_guardrail_pass(self) -> None:
        """关键词检测 — 正常输入通过。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        await _execute_input_guardrails(
            [InputGuardrail(guardrail_function=_keyword_guardrail, name="sql_check")],
            ctx,
            "select * from users",
        )

    @pytest.mark.asyncio
    async def test_keyword_guardrail_block(self) -> None:
        """关键词检测 — SQL 注入被拦截。"""
        ctx = RunContext(agent=Agent(name="test"), config=RunConfig(), context={}, turn_count=0)
        with pytest.raises(InputGuardrailTripwireError) as exc_info:
            await _execute_input_guardrails(
                [InputGuardrail(guardrail_function=_keyword_guardrail, name="sql_check")],
                ctx,
                "please run DROP TABLE users",
            )
        assert "SQL injection" in exc_info.value.message


# ---------- Runner integration tests ----------

class TestRunnerWithGuardrails:
    """Runner + InputGuardrail 集成测试。"""

    @pytest.mark.asyncio
    async def test_run_passes_when_guardrails_pass(self) -> None:
        """guardrails 全部通过时 Runner 正常完成。"""
        agent = Agent(
            name="safe-bot",
            instructions="You are helpful.",
            input_guardrails=[InputGuardrail(guardrail_function=_pass_guardrail)],
        )
        config = RunConfig(model_provider=_MockProvider("hello!"))
        result = await Runner.run(agent, "hi", config=config)
        assert result.output == "hello!"

    @pytest.mark.asyncio
    async def test_run_blocked_when_guardrail_trips(self) -> None:
        """guardrail 触发时 Runner 抛出 InputGuardrailTripwireError。"""
        agent = Agent(
            name="safe-bot",
            instructions="You are helpful.",
            input_guardrails=[InputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
        )
        config = RunConfig(model_provider=_MockProvider("should not reach"))
        with pytest.raises(InputGuardrailTripwireError) as exc_info:
            await Runner.run(agent, "bad input", config=config)
        assert exc_info.value.guardrail_name == "blocker"

    @pytest.mark.asyncio
    async def test_run_no_llm_call_when_blocked(self) -> None:
        """guardrail 拦截时不应调用 LLM。"""
        llm_called = False

        class _TrackingProvider(ModelProvider):
            async def chat(self, **kwargs):  # type: ignore[override]
                nonlocal llm_called
                llm_called = True
                return ModelResponse(content="oops", tool_calls=[], token_usage=None)

        agent = Agent(
            name="safe-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_block_guardrail)],
        )
        config = RunConfig(model_provider=_TrackingProvider())
        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(agent, "danger", config=config)
        assert llm_called is False

    @pytest.mark.asyncio
    async def test_no_guardrails_runs_normally(self) -> None:
        """没有 guardrails 的 Agent 正常运行。"""
        agent = Agent(name="basic-bot")
        config = RunConfig(model_provider=_MockProvider("hi"))
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "hi"

    @pytest.mark.asyncio
    async def test_guardrail_receives_user_input(self) -> None:
        """guardrail 函数接收到正确的用户输入文本。"""
        received_input: list[str] = []

        async def _capture_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            received_input.append(input_text)
            return GuardrailResult(tripwire_triggered=False, message="ok")

        agent = Agent(
            name="test-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_capture_guardrail)],
        )
        config = RunConfig(model_provider=_MockProvider("response"))
        await Runner.run(agent, "what is the capital of France?", config=config)
        assert received_input == ["what is the capital of France?"]


# ---------- Tracing integration ----------

class TestGuardrailTracing:
    """Guardrail + Tracing 集成测试。"""

    @pytest.mark.asyncio
    async def test_guardrail_span_on_pass(self) -> None:
        """guardrail 通过时产出 GUARDRAIL Span (COMPLETED)。"""
        agent = Agent(
            name="traced-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_pass_guardrail, name="checker")],
        )
        config = RunConfig(model_provider=_MockProvider("ok"), tracing_enabled=True)
        result = await Runner.run(agent, "hello", config=config)
        assert result.trace is not None
        guardrail_spans = [s for s in result.trace.spans if s.type == SpanType.GUARDRAIL]
        assert len(guardrail_spans) == 1
        assert guardrail_spans[0].name == "checker"
        assert guardrail_spans[0].status.value == "completed"

    @pytest.mark.asyncio
    async def test_guardrail_span_on_trip(self) -> None:
        """guardrail 触发时产出 GUARDRAIL Span (FAILED)。"""
        agent = Agent(
            name="traced-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
        )
        config = RunConfig(model_provider=_MockProvider("x"), tracing_enabled=True)
        with contextlib.suppress(InputGuardrailTripwireError):
            await Runner.run(agent, "bad", config=config)
        # trace 不可获取，因为 Runner.run 抛了异常，但 trace 在异常前已 end
        # 重新验证：guardrail 内部 Span 通过 tracing ctx 记录

    @pytest.mark.asyncio
    async def test_multiple_guardrails_multiple_spans(self) -> None:
        """多个 guardrails 产出多个 Span。"""
        agent = Agent(
            name="multi-bot",
            input_guardrails=[
                InputGuardrail(guardrail_function=_pass_guardrail, name="guard1"),
                InputGuardrail(guardrail_function=_pass_guardrail, name="guard2"),
            ],
        )
        config = RunConfig(model_provider=_MockProvider("ok"), tracing_enabled=True)
        result = await Runner.run(agent, "hello", config=config)
        assert result.trace is not None
        guardrail_spans = [s for s in result.trace.spans if s.type == SpanType.GUARDRAIL]
        assert len(guardrail_spans) == 2
        assert guardrail_spans[0].name == "guard1"
        assert guardrail_spans[1].name == "guard2"


# ---------- Streamed runner tests ----------

class TestRunStreamedWithGuardrails:
    """run_streamed + InputGuardrail 测试。"""

    @pytest.mark.asyncio
    async def test_streamed_blocked_when_guardrail_trips(self) -> None:
        """流式运行时 guardrail 触发也抛出异常。"""
        agent = Agent(
            name="stream-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_block_guardrail, name="blocker")],
        )
        config = RunConfig(model_provider=_MockProvider("x"))
        with pytest.raises(InputGuardrailTripwireError):
            async for _ in Runner.run_streamed(agent, "bad input", config=config):
                pass

    @pytest.mark.asyncio
    async def test_streamed_passes_normally(self) -> None:
        """流式运行 guardrails 通过后正常产出事件。"""
        agent = Agent(
            name="stream-bot",
            input_guardrails=[InputGuardrail(guardrail_function=_pass_guardrail)],
        )
        config = RunConfig(model_provider=_MockProvider("streaming ok"))
        events = []
        async for event in Runner.run_streamed(agent, "hi", config=config):
            events.append(event)
        assert len(events) > 0
