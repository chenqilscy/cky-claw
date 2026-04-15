"""Approval Mode 测试。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import (
    ApprovalDecision,
    ApprovalMode,
    ApprovalRejectedError,
)
from ckyclaw_framework.model.message import TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import function_tool

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext

# ---------- helpers ----------

class _AutoApproveHandler(ApprovalHandler):
    """始终批准的审批处理器。"""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        self.requests.append({"action_type": action_type, "action_detail": action_detail})
        return ApprovalDecision.APPROVED


class _AutoRejectHandler(ApprovalHandler):
    """始终拒绝的审批处理器。"""

    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        return ApprovalDecision.REJECTED


class _TimeoutHandler(ApprovalHandler):
    """始终超时的审批处理器。"""

    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        return ApprovalDecision.TIMEOUT


@function_tool()
def get_weather(city: str) -> str:
    """获取天气信息。"""
    return f"{city} 晴天 25°C"


class _ToolCallProvider(ModelProvider):
    """第一轮返回 tool_call，第二轮返回最终文本。"""

    def __init__(self, tool_name: str = "get_weather", tool_args: str = '{"city":"北京"}') -> None:
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._call_count = 0

    async def chat(self, **kwargs) -> ModelResponse:  # type: ignore[override]
        self._call_count += 1
        stream = kwargs.get("stream", False)
        if stream:
            return self._stream()  # type: ignore[return-value]
        if self._call_count == 1:
            return ModelResponse(
                content=None,
                tool_calls=[ToolCall(id="tc_1", name=self._tool_name, arguments=self._tool_args)],
                token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        return ModelResponse(
            content="天气查询完成",
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=15, completion_tokens=10, total_tokens=25),
        )

    async def _stream(self):
        yield ModelChunk(content="streaming", finish_reason="stop")


class _TextOnlyProvider(ModelProvider):
    """直接返回文本（无工具调用）。"""

    async def chat(self, **kwargs) -> ModelResponse:  # type: ignore[override]
        return ModelResponse(
            content="hello",
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )


# ---------- ApprovalMode enum tests ----------

class TestApprovalMode:
    """ApprovalMode 枚举测试。"""

    def test_values(self) -> None:
        assert ApprovalMode.SUGGEST == "suggest"
        assert ApprovalMode.AUTO_EDIT == "auto-edit"
        assert ApprovalMode.FULL_AUTO == "full-auto"

    def test_decision_values(self) -> None:
        assert ApprovalDecision.APPROVED == "approved"
        assert ApprovalDecision.REJECTED == "rejected"
        assert ApprovalDecision.TIMEOUT == "timeout"

    def test_rejected_error(self) -> None:
        err = ApprovalRejectedError("my_tool", "not allowed")
        assert err.tool_name == "my_tool"
        assert err.reason == "not allowed"
        assert "my_tool" in str(err)


# ---------- Runner + full-auto (default) ----------

class TestFullAutoMode:
    """full-auto 模式下工具直接执行，无需审批。"""

    @pytest.mark.asyncio
    async def test_tool_call_no_approval(self) -> None:
        agent = Agent(name="bot", tools=[get_weather])
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "北京天气", config=config)
        assert "天气" in result.output

    @pytest.mark.asyncio
    async def test_explicit_full_auto(self) -> None:
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.FULL_AUTO)
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "北京天气", config=config)
        assert "天气" in result.output


# ---------- Runner + suggest mode ----------

class TestSuggestMode:
    """suggest 模式下所有工具调用需审批。"""

    @pytest.mark.asyncio
    async def test_approved_tool_call(self) -> None:
        """审批通过 → 工具正常执行。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=handler)
        result = await Runner.run(agent, "北京天气", config=config)
        assert "天气" in result.output
        # 验证 handler 收到了请求
        assert len(handler.requests) == 1
        assert handler.requests[0]["action_type"] == "tool_call"
        assert handler.requests[0]["action_detail"]["tool_name"] == "get_weather"

    @pytest.mark.asyncio
    async def test_rejected_tool_call_becomes_error(self) -> None:
        """审批拒绝 → 工具结果变为错误消息（不中断 Run）。"""
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=_AutoRejectHandler())
        result = await Runner.run(agent, "北京天气", config=config)
        # LLM 第二轮会收到拒绝错误作为 tool result，然后返回最终文本
        assert result.output  # Runner 不会 crash

    @pytest.mark.asyncio
    async def test_timeout_becomes_error(self) -> None:
        """审批超时 → 工具结果变为错误消息。"""
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=_TimeoutHandler())
        result = await Runner.run(agent, "北京天气", config=config)
        assert result.output  # Runner 不会 crash

    @pytest.mark.asyncio
    async def test_suggest_without_handler_returns_error(self) -> None:
        """suggest 模式没有 handler → 工具调用被拒（变为 tool error）。"""
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider())
        result = await Runner.run(agent, "北京天气", config=config)
        assert result.output  # 不会 crash，LLM 收到 error tool result

    @pytest.mark.asyncio
    async def test_no_tool_call_no_approval_needed(self) -> None:
        """suggest 模式下无工具调用 → 不触发审批。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_TextOnlyProvider(), approval_handler=handler)
        result = await Runner.run(agent, "hi", config=config)
        assert result.output == "hello"
        assert len(handler.requests) == 0  # 没有审批请求


# ---------- RunConfig override ----------

class TestApprovalModeOverride:
    """RunConfig approval_mode 覆盖 Agent approval_mode。"""

    @pytest.mark.asyncio
    async def test_config_overrides_agent(self) -> None:
        """Agent 设为 suggest，RunConfig 设为 full-auto → 不审批。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(
            model_provider=_ToolCallProvider(),
            approval_mode=ApprovalMode.FULL_AUTO,
            approval_handler=handler,
        )
        result = await Runner.run(agent, "北京天气", config=config)
        assert "天气" in result.output
        assert len(handler.requests) == 0  # full-auto 不审批

    @pytest.mark.asyncio
    async def test_agent_mode_used_when_no_config(self) -> None:
        """RunConfig 没设 approval_mode → 使用 Agent 的 mode。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=handler)
        await Runner.run(agent, "北京天气", config=config)
        assert len(handler.requests) == 1  # suggest → 触发审批


# ---------- auto-edit mode ----------

class TestAutoEditMode:
    """auto-edit 模式测试（MVP 阶段等同 full-auto）。"""

    @pytest.mark.asyncio
    async def test_auto_edit_no_approval(self) -> None:
        """auto-edit MVP 阶段直接执行，不审批。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.AUTO_EDIT)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=handler)
        result = await Runner.run(agent, "北京天气", config=config)
        assert "天气" in result.output
        assert len(handler.requests) == 0


# ---------- Handler detail tests ----------

class TestApprovalHandlerDetail:
    """ApprovalHandler 接口详细测试。"""

    @pytest.mark.asyncio
    async def test_handler_receives_correct_detail(self) -> None:
        """handler.request_approval 接收正确的 tool_name 和 arguments。"""
        handler = _AutoApproveHandler()
        agent = Agent(name="bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=handler)
        await Runner.run(agent, "北京天气", config=config)
        detail = handler.requests[0]["action_detail"]
        assert detail["tool_name"] == "get_weather"
        args = detail["arguments"]
        assert args["city"] == "北京"

    @pytest.mark.asyncio
    async def test_handler_receives_run_context(self) -> None:
        """handler.request_approval 接收到 RunContext。"""
        received_contexts: list[RunContext] = []

        class _ContextCapture(ApprovalHandler):
            async def request_approval(
                self, run_context: RunContext, action_type: str,
                action_detail: dict[str, Any], timeout: int = 300,
            ) -> ApprovalDecision:
                received_contexts.append(run_context)
                return ApprovalDecision.APPROVED

        agent = Agent(name="ctx-bot", tools=[get_weather], approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(model_provider=_ToolCallProvider(), approval_handler=_ContextCapture())
        await Runner.run(agent, "test", config=config)
        assert len(received_contexts) == 1
        assert received_contexts[0].agent.name == "ctx-bot"
