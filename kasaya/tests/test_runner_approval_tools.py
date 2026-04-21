"""Runner 审批 + 工具执行函数单元测试 — 覆盖 _check_approval / _execute_tool_calls / _resolve_approval_mode。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from kasaya.agent.agent import Agent
from kasaya.approval.handler import ApprovalHandler
from kasaya.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError
from kasaya.guardrails.result import GuardrailResult
from kasaya.guardrails.tool_guardrail import ToolGuardrail
from kasaya.model.provider import ToolCall
from kasaya.runner.run_config import RunConfig
from kasaya.runner.run_context import RunContext
from kasaya.runner.runner import (
    _check_approval,
    _execute_tool_calls,
    _resolve_approval_mode,
)
from kasaya.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from kasaya.model.message import Message


def _agent(**kwargs: Any) -> Agent:
    """快捷创建测试 Agent。"""
    defaults: dict[str, Any] = {"name": "test_agent", "instructions": "test"}
    defaults.update(kwargs)
    return Agent(**defaults)


def _ctx(agent: Agent | None = None) -> RunContext:
    """创建测试用 RunContext。"""
    a = agent or _agent()
    return RunContext(agent=a, config=RunConfig(), context={})


def _make_tool(name: str = "my_tool", result: str = "ok", **kwargs: Any) -> FunctionTool:
    """创建简单的 FunctionTool。"""
    async def fn(**args: Any) -> str:
        return result

    return FunctionTool(
        name=name,
        description=f"Tool {name}",
        parameters_schema={"type": "object", "properties": {}},
        fn=fn,
        **kwargs,
    )


# ─── _resolve_approval_mode ─────────────────────────────────────

class TestResolveApprovalMode:
    """_resolve_approval_mode 优先级测试。"""

    def test_config_overrides_agent(self) -> None:
        agent = _agent(approval_mode=ApprovalMode.SUGGEST)
        config = RunConfig(approval_mode=ApprovalMode.FULL_AUTO)
        assert _resolve_approval_mode(agent, config) == ApprovalMode.FULL_AUTO

    def test_agent_default(self) -> None:
        agent = _agent(approval_mode=ApprovalMode.SUGGEST)
        assert _resolve_approval_mode(agent, None) == ApprovalMode.SUGGEST

    def test_fallback_full_auto(self) -> None:
        agent = _agent()
        assert _resolve_approval_mode(agent, RunConfig()) == ApprovalMode.FULL_AUTO


# ─── _check_approval ─────────────────────────────────────────────

class TestCheckApproval:
    """_check_approval 审批检查测试。"""

    @pytest.mark.asyncio
    async def test_full_auto_returns_immediately(self) -> None:
        """FULL_AUTO 模式直接返回（line 400）。"""
        await _check_approval(_ctx(), None, ApprovalMode.FULL_AUTO, "any_tool", {})

    @pytest.mark.asyncio
    async def test_auto_edit_safe_tool(self) -> None:
        """AUTO_EDIT 模式：安全工具（get_前缀）直接返回（line 407）。"""
        await _check_approval(_ctx(), None, ApprovalMode.AUTO_EDIT, "get_users", {})

    @pytest.mark.asyncio
    async def test_auto_edit_risky_no_handler(self) -> None:
        """AUTO_EDIT 模式：高风险工具无 handler → 拒绝。"""
        with pytest.raises(ApprovalRejectedError, match="no ApprovalHandler"):
            await _check_approval(
                _ctx(), None, ApprovalMode.AUTO_EDIT, "delete_file", {},
            )

    @pytest.mark.asyncio
    async def test_auto_edit_risky_approved(self) -> None:
        """AUTO_EDIT 模式：高风险工具 → handler 批准。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.APPROVED)
        await _check_approval(
            _ctx(), handler, ApprovalMode.AUTO_EDIT, "delete_file", {"path": "/tmp"},
        )
        handler.request_approval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_edit_risky_rejected(self) -> None:
        """AUTO_EDIT 模式：高风险工具 → handler 拒绝（line 514）。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.REJECTED)
        with pytest.raises(ApprovalRejectedError, match="rejected by approver"):
            await _check_approval(
                _ctx(), handler, ApprovalMode.AUTO_EDIT, "delete_file", {},
            )

    @pytest.mark.asyncio
    async def test_auto_edit_risky_timeout(self) -> None:
        """AUTO_EDIT 模式：高风险工具 → handler 超时（line 528）。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.TIMEOUT)
        with pytest.raises(ApprovalRejectedError, match="timed out"):
            await _check_approval(
                _ctx(), handler, ApprovalMode.AUTO_EDIT, "delete_file", {},
            )

    @pytest.mark.asyncio
    async def test_auto_edit_approval_required_flag(self) -> None:
        """AUTO_EDIT 模式：tool_approval_required=True 强制审批。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.APPROVED)
        await _check_approval(
            _ctx(), handler, ApprovalMode.AUTO_EDIT, "get_data", {},
            tool_approval_required=True,
        )
        handler.request_approval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_suggest_no_handler(self) -> None:
        """SUGGEST 模式：无 handler → 拒绝。"""
        with pytest.raises(ApprovalRejectedError, match="suggest mode requires"):
            await _check_approval(
                _ctx(), None, ApprovalMode.SUGGEST, "any_tool", {},
            )

    @pytest.mark.asyncio
    async def test_suggest_approved(self) -> None:
        """SUGGEST 模式：handler 批准。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.APPROVED)
        await _check_approval(
            _ctx(), handler, ApprovalMode.SUGGEST, "any_tool", {},
        )

    @pytest.mark.asyncio
    async def test_suggest_rejected(self) -> None:
        """SUGGEST 模式：handler 拒绝。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.REJECTED)
        with pytest.raises(ApprovalRejectedError, match="rejected"):
            await _check_approval(
                _ctx(), handler, ApprovalMode.SUGGEST, "any_tool", {},
            )

    @pytest.mark.asyncio
    async def test_suggest_timeout(self) -> None:
        """SUGGEST 模式：handler 超时。"""
        handler = AsyncMock(spec=ApprovalHandler)
        handler.request_approval = AsyncMock(return_value=ApprovalDecision.TIMEOUT)
        with pytest.raises(ApprovalRejectedError, match="timed out"):
            await _check_approval(
                _ctx(), handler, ApprovalMode.SUGGEST, "any_tool", {},
            )


# ─── _execute_tool_calls ─────────────────────────────────────────

class TestExecuteToolCalls:
    """_execute_tool_calls 工具执行测试。"""

    @pytest.mark.asyncio
    async def test_single_tool_success(self) -> None:
        """单个工具成功执行。"""
        tool = _make_tool("greet", "hello world")
        agent = _agent(tools=[tool])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="greet", arguments="{}")

        result = await _execute_tool_calls(agent, [tc], messages)
        assert result is None  # 非 Handoff
        assert len(messages) == 1
        assert "hello world" in messages[0].content

    @pytest.mark.asyncio
    async def test_tool_not_found(self) -> None:
        """工具未找到 → Error 消息（lines 598-599）。"""
        agent = _agent(tools=[])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="unknown_tool", arguments="{}")

        await _execute_tool_calls(agent, [tc], messages)
        assert len(messages) == 1
        assert "not found" in messages[0].content

    @pytest.mark.asyncio
    async def test_json_decode_error(self) -> None:
        """arguments 非法 JSON → 空 dict fallback（line 618）。"""
        call_args: dict[str, Any] = {}

        async def capture_fn(**kwargs: Any) -> str:
            call_args.update(kwargs)
            return "ok"

        tool = FunctionTool(
            name="cap",
            description="d",
            parameters_schema={"type": "object", "properties": {}},
            fn=capture_fn,
        )
        agent = _agent(tools=[tool])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="cap", arguments="not-json{{{")

        await _execute_tool_calls(agent, [tc], messages)
        assert len(messages) == 1
        # 工具仍应执行，arguments fallback 为 {}

    @pytest.mark.asyncio
    async def test_tool_exception(self) -> None:
        """工具执行异常 → Error 消息。"""
        async def failing(**kwargs: Any) -> str:
            raise RuntimeError("tool error")

        tool = FunctionTool(name="fail", description="d", parameters_schema={}, fn=failing)
        agent = _agent(tools=[tool])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="fail", arguments="{}")

        await _execute_tool_calls(agent, [tc], messages)
        assert "Error" in messages[0].content

    @pytest.mark.asyncio
    async def test_tool_timeout(self) -> None:
        """工具执行超时 → Error 消息。"""
        import asyncio

        async def slow_fn(**kwargs: Any) -> str:
            await asyncio.sleep(10)
            return "done"

        tool = FunctionTool(name="slow", description="d", parameters_schema={}, fn=slow_fn)
        agent = _agent(tools=[tool])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="slow", arguments="{}")
        config = RunConfig(tool_timeout=0.01)

        await _execute_tool_calls(agent, [tc], messages, config=config)
        assert "timed out" in messages[0].content

    @pytest.mark.asyncio
    async def test_multiple_tools_parallel(self) -> None:
        """多个工具并行执行（TaskGroup 分支）。"""
        tool_a = _make_tool("tool_a", "result_a")
        tool_b = _make_tool("tool_b", "result_b")
        agent = _agent(tools=[tool_a, tool_b])
        messages: list[Message] = []
        tcs = [
            ToolCall(id="tc1", name="tool_a", arguments="{}"),
            ToolCall(id="tc2", name="tool_b", arguments="{}"),
        ]

        result = await _execute_tool_calls(agent, tcs, messages)
        assert result is None
        assert len(messages) == 2
        contents = [m.content for m in messages]
        assert any("result_a" in c for c in contents)
        assert any("result_b" in c for c in contents)

    @pytest.mark.asyncio
    async def test_max_concurrency_semaphore(self) -> None:
        """max_tool_concurrency 限流路径。"""
        tool = _make_tool("t", "ok")
        agent = _agent(tools=[tool])
        messages: list[Message] = []
        tcs = [
            ToolCall(id="tc1", name="t", arguments="{}"),
            ToolCall(id="tc2", name="t", arguments="{}"),
        ]
        config = RunConfig(max_tool_concurrency=1)

        await _execute_tool_calls(agent, tcs, messages, config=config)
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_handoff_detection(self) -> None:
        """Handoff 工具调用 → 返回 (target_agent, config)。"""
        target = _agent(name="agent_b")
        src = _agent(name="agent_a", handoffs=[target])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="transfer_to_agent_b", arguments="{}")

        result = await _execute_tool_calls(src, [tc], messages)
        assert result is not None
        assert result[0].name == "agent_b"

    @pytest.mark.asyncio
    async def test_handoff_with_preceding_tools(self) -> None:
        """Handoff 前有普通工具 → 先执行普通工具再处理 Handoff。"""
        tool = _make_tool("greet", "hello")
        target = _agent(name="agent_b")
        src = _agent(name="agent_a", tools=[tool], handoffs=[target])
        messages: list[Message] = []
        tcs = [
            ToolCall(id="tc1", name="greet", arguments="{}"),
            ToolCall(id="tc2", name="transfer_to_agent_b", arguments="{}"),
        ]

        result = await _execute_tool_calls(src, tcs, messages)
        assert result is not None  # Handoff 返回
        assert result[0].name == "agent_b"
        # greet 的结果应该在 messages 中
        assert any("hello" in m.content for m in messages)

    @pytest.mark.asyncio
    async def test_tool_guardrail_before_blocks(self) -> None:
        """Tool Guardrail before_fn 触发 → 工具不执行。"""
        tool = _make_tool("dangerous", "should not run")
        agent = _agent(tools=[tool])

        async def block_before(ctx: RunContext, tool_name: str, args: dict) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="blocked by guardrail")

        tg = ToolGuardrail(name="block_guard", before_fn=block_before)
        config = RunConfig(tool_guardrails=[tg])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="dangerous", arguments="{}")

        await _execute_tool_calls(
            agent, [tc], messages, run_context=_ctx(agent), config=config,
        )
        assert "blocked" in messages[0].content.lower()

    @pytest.mark.asyncio
    async def test_tool_guardrail_after_blocks(self) -> None:
        """Tool Guardrail after_fn 触发 → 替换工具结果。"""
        tool = _make_tool("leaky", "sensitive data")
        agent = _agent(tools=[tool])

        async def block_after(ctx: RunContext, tool_name: str, result: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="data leak detected")

        tg = ToolGuardrail(name="leak_guard", after_fn=block_after)
        config = RunConfig(tool_guardrails=[tg])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="leaky", arguments="{}")

        await _execute_tool_calls(
            agent, [tc], messages, run_context=_ctx(agent), config=config,
        )
        assert "data leak" in messages[0].content.lower()

    @pytest.mark.asyncio
    async def test_tool_guardrail_before_exception(self) -> None:
        """Tool Guardrail before_fn 抛异常 → 转为 tripwire。"""
        tool = _make_tool("t", "ok")
        agent = _agent(tools=[tool])

        async def err_before(ctx: RunContext, tool_name: str, args: dict) -> GuardrailResult:
            raise RuntimeError("guardrail crash")

        tg = ToolGuardrail(name="err_guard", before_fn=err_before)
        config = RunConfig(tool_guardrails=[tg])
        messages: list[Message] = []
        tc = ToolCall(id="tc1", name="t", arguments="{}")

        await _execute_tool_calls(
            agent, [tc], messages, run_context=_ctx(agent), config=config,
        )
        assert "blocked" in messages[0].content.lower() or "guardrail" in messages[0].content.lower()
