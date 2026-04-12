"""RunConfig.environment 环境感知运行测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelProvider, ModelResponse
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.trace import Trace


class _SimpleProvider(ModelProvider):
    """固定返回文本。"""

    async def chat(self, **kwargs):  # type: ignore[override]
        return ModelResponse(
            content="ok",
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=2),
        )


class _CapturingProcessor(TraceProcessor):
    """捕获 Trace 的处理器。"""

    def __init__(self) -> None:
        self.traces: list[Trace] = []

    async def on_trace_start(self, trace: Trace) -> None:
        pass

    async def on_trace_end(self, trace: Trace) -> None:
        self.traces.append(trace)

    async def on_span_start(self, span) -> None:  # type: ignore[override]
        pass

    async def on_span_end(self, span) -> None:  # type: ignore[override]
        pass


@pytest.mark.asyncio
async def test_environment_in_trace_metadata():
    """RunConfig.environment 传播到 Trace.metadata。"""
    agent = Agent(name="env-test", instructions="test", model="mock")
    proc = _CapturingProcessor()

    config = RunConfig(
        model_provider=_SimpleProvider(),
        environment="staging",
        trace_processors=[proc],
    )
    result = await Runner.run(
        agent,
        input=[Message(role=MessageRole.USER, content="hi")],
        config=config,
    )
    assert result.output == "ok"
    assert len(proc.traces) == 1
    assert proc.traces[0].metadata.get("environment") == "staging"


@pytest.mark.asyncio
async def test_no_environment_no_metadata():
    """不设置 environment 时，metadata 不包含 environment。"""
    agent = Agent(name="env-test2", instructions="test", model="mock")
    proc = _CapturingProcessor()

    config = RunConfig(
        model_provider=_SimpleProvider(),
        trace_processors=[proc],
    )
    result = await Runner.run(
        agent,
        input=[Message(role=MessageRole.USER, content="hi")],
        config=config,
    )
    assert result.output == "ok"
    assert len(proc.traces) == 1
    assert "environment" not in proc.traces[0].metadata


@pytest.mark.asyncio
async def test_trace_metadata_field_exists():
    """Trace dataclass 有 metadata 字段并默认为空 dict。"""
    t = Trace()
    assert isinstance(t.metadata, dict)
    assert len(t.metadata) == 0
