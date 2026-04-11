"""DebugController 单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from ckyclaw_framework.debug.controller import (
    DebugController,
    DebugEvent,
    DebugEventType,
    DebugMode,
    DebugState,
    PauseContext,
)
from ckyclaw_framework.model.message import Message, MessageRole


# === 辅助工具 ===


def _make_messages(n: int = 3) -> list[Message]:
    """创建测试消息列表。"""
    msgs = []
    for i in range(n):
        role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
        msgs.append(Message(role=role, content=f"msg-{i}"))
    return msgs


class TestDebugControllerInit:
    """初始化测试。"""

    def test_default_mode(self) -> None:
        """默认模式为 STEP_TURN。"""
        ctrl = DebugController()
        assert ctrl.mode == DebugMode.STEP_TURN

    def test_custom_mode(self) -> None:
        """自定义调试模式。"""
        ctrl = DebugController(mode=DebugMode.STEP_TOOL)
        assert ctrl.mode == DebugMode.STEP_TOOL

    def test_initial_state_idle(self) -> None:
        """初始状态为 IDLE。"""
        ctrl = DebugController()
        assert ctrl.state == DebugState.IDLE

    def test_pause_context_none(self) -> None:
        """初始暂停上下文为 None。"""
        ctrl = DebugController()
        assert ctrl.pause_context is None


class TestDebugModeSwitching:
    """调试模式切换测试。"""

    def test_switch_mode(self) -> None:
        """运行时切换调试模式。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        ctrl.mode = DebugMode.CONTINUE
        assert ctrl.mode == DebugMode.CONTINUE


class TestCheckpointPauseBehavior:
    """checkpoint 暂停行为测试。"""

    @pytest.mark.asyncio
    async def test_step_turn_pauses_on_turn_end(self) -> None:
        """STEP_TURN 模式：turn_end 触发暂停。"""
        events: list[DebugEvent] = []

        async def on_event(e: DebugEvent) -> None:
            events.append(e)

        ctrl = DebugController(mode=DebugMode.STEP_TURN, on_event=on_event)
        msgs = _make_messages()

        # 在后台运行 checkpoint（会阻塞）
        async def run_checkpoint() -> None:
            await ctrl.checkpoint(
                reason="turn_end", turn=1, agent_name="agent_a",
                messages=msgs, token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            )

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)  # 等 checkpoint 进入暂停

        assert ctrl.state == DebugState.PAUSED
        assert ctrl.pause_context is not None
        assert ctrl.pause_context.turn == 1
        assert ctrl.pause_context.agent_name == "agent_a"
        assert ctrl.pause_context.reason == "turn_end"
        assert len(events) == 1
        assert events[0].type == DebugEventType.PAUSED

        # 恢复执行
        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

    @pytest.mark.asyncio
    async def test_step_tool_pauses_on_before_tool(self) -> None:
        """STEP_TOOL 模式：before_tool 触发暂停。"""
        ctrl = DebugController(mode=DebugMode.STEP_TOOL)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(
                reason="before_tool", turn=1, agent_name="agent_b",
                messages=msgs,
            )

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.state == DebugState.PAUSED
        assert ctrl.pause_context is not None
        assert ctrl.pause_context.reason == "before_tool"

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

    @pytest.mark.asyncio
    async def test_step_turn_does_not_pause_on_before_tool(self) -> None:
        """STEP_TURN 模式：before_tool 不触发暂停。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        # 不应阻塞
        await ctrl.checkpoint(
            reason="before_tool", turn=1, agent_name="agent_c",
            messages=msgs,
        )
        # 到这里说明没有阻塞
        assert ctrl.state == DebugState.RUNNING

    @pytest.mark.asyncio
    async def test_continue_mode_does_not_pause(self) -> None:
        """CONTINUE 模式：不暂停。"""
        ctrl = DebugController(mode=DebugMode.CONTINUE)
        msgs = _make_messages()

        await ctrl.checkpoint(
            reason="turn_end", turn=1, agent_name="agent_d",
            messages=msgs,
        )
        assert ctrl.state == DebugState.RUNNING

    @pytest.mark.asyncio
    async def test_handoff_pauses_in_step_turn(self) -> None:
        """STEP_TURN 模式：before_handoff 触发暂停。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(
                reason="before_handoff", turn=2, agent_name="agent_src",
                messages=msgs,
            )

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.state == DebugState.PAUSED
        assert ctrl.pause_context is not None
        assert ctrl.pause_context.reason == "before_handoff"

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task


class TestControlActions:
    """用户控制操作测试。"""

    @pytest.mark.asyncio
    async def test_step_resumes_and_pauses_next(self) -> None:
        """step() 操作后到下一个 checkpoint 再次暂停。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        # 第 1 次 checkpoint — 暂停
        async def first_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(first_checkpoint())
        await asyncio.sleep(0.05)
        assert ctrl.state == DebugState.PAUSED

        # step() — 继续 + 设置 _pending_action="step"
        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

        # 第 2 次 checkpoint — 应该再次暂停（因为 step 语义）
        # 但此时 _pending_action 已被 step() 设置，不过 checkpoint 内部在
        # should_pause 后清除了，所以需要新的 step 触发
        # 实际上 step_turn 模式本身就 turn_end 暂停
        async def second_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=2, agent_name="a", messages=msgs)

        task2 = asyncio.create_task(second_checkpoint())
        await asyncio.sleep(0.05)
        assert ctrl.state == DebugState.PAUSED
        assert ctrl.pause_context is not None
        assert ctrl.pause_context.turn == 2

        await ctrl.resume()
        await asyncio.sleep(0.05)
        await task2

    @pytest.mark.asyncio
    async def test_resume_switches_to_continue_mode(self) -> None:
        """resume() 将模式切换为 CONTINUE。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)
        assert ctrl.state == DebugState.PAUSED

        await ctrl.resume()
        await asyncio.sleep(0.05)
        await task

        assert ctrl.mode == DebugMode.CONTINUE

        # 后续 checkpoint 不再暂停
        await ctrl.checkpoint(reason="turn_end", turn=2, agent_name="a", messages=msgs)
        assert ctrl.state == DebugState.RUNNING

    @pytest.mark.asyncio
    async def test_stop_cancels_execution(self) -> None:
        """stop() 终止调试会话。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)
        assert ctrl.state == DebugState.PAUSED

        await ctrl.stop()
        with pytest.raises(asyncio.CancelledError, match="stopped by user"):
            await task


class TestPauseContextSnapshot:
    """暂停上下文快照测试。"""

    @pytest.mark.asyncio
    async def test_recent_messages_limited_to_5(self) -> None:
        """快照最多保留最近 5 条消息。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages(10)

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.pause_context is not None
        assert len(ctrl.pause_context.recent_messages) == 5

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

    @pytest.mark.asyncio
    async def test_llm_snapshot_in_pause_context(self) -> None:
        """暂停上下文包含 LLM 响应快照。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        ctrl.snapshot_llm_response({"content": "hello", "tool_calls": []})
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.pause_context is not None
        assert ctrl.pause_context.last_llm_response == {"content": "hello", "tool_calls": []}

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

    @pytest.mark.asyncio
    async def test_tool_snapshot_in_pause_context(self) -> None:
        """暂停上下文包含工具调用快照。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        ctrl.snapshot_tool_call("search", {"query": "test"}, result="ok")
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.pause_context is not None
        assert ctrl.pause_context.last_tool_calls is not None
        assert len(ctrl.pause_context.last_tool_calls) == 1
        assert ctrl.pause_context.last_tool_calls[0]["tool_name"] == "search"

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

    @pytest.mark.asyncio
    async def test_token_usage_in_pause_context(self) -> None:
        """暂停上下文包含 Token 统计。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(
                reason="turn_end", turn=1, agent_name="a",
                messages=msgs,
                token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            )

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.pause_context is not None
        assert ctrl.pause_context.token_usage["total_tokens"] == 150

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task


class TestPauseTimeout:
    """暂停超时测试。"""

    @pytest.mark.asyncio
    async def test_pause_timeout_cancels(self) -> None:
        """暂停超时后自动终止。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN, pause_timeout=0.1)
        msgs = _make_messages()

        with pytest.raises(asyncio.CancelledError, match="timed out"):
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        assert ctrl.state == DebugState.TIMEOUT


class TestEventCallback:
    """事件回调测试。"""

    @pytest.mark.asyncio
    async def test_events_emitted_on_pause_and_step(self) -> None:
        """暂停和步进时推送事件。"""
        events: list[DebugEvent] = []

        async def on_event(e: DebugEvent) -> None:
            events.append(e)

        ctrl = DebugController(mode=DebugMode.STEP_TURN, on_event=on_event)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].type == DebugEventType.PAUSED

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task

        assert len(events) == 2
        assert events[1].type == DebugEventType.STEP

    @pytest.mark.asyncio
    async def test_event_callback_error_ignored(self) -> None:
        """事件回调异常不影响执行。"""

        async def on_event(e: DebugEvent) -> None:
            raise RuntimeError("callback error")

        ctrl = DebugController(mode=DebugMode.STEP_TURN, on_event=on_event)
        msgs = _make_messages()

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        # 即使回调异常，仍然已暂停
        assert ctrl.state == DebugState.PAUSED

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task


class TestMarkCompletedFailed:
    """完成/失败标记测试。"""

    def test_mark_completed(self) -> None:
        """mark_completed 设置 COMPLETED 状态。"""
        ctrl = DebugController()
        ctrl.mark_completed()
        assert ctrl.state == DebugState.COMPLETED

    def test_mark_failed(self) -> None:
        """mark_failed 设置 FAILED 状态。"""
        ctrl = DebugController()
        ctrl.mark_failed()
        assert ctrl.state == DebugState.FAILED

    @pytest.mark.asyncio
    async def test_checkpoint_no_op_after_completed(self) -> None:
        """COMPLETED 后 checkpoint 不再暂停。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        ctrl.mark_completed()
        msgs = _make_messages()

        # 不应阻塞
        await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)
        assert ctrl.state == DebugState.COMPLETED


class TestClearToolSnapshots:
    """工具快照清理测试。"""

    def test_clear_tool_snapshots(self) -> None:
        """clear_tool_snapshots 清空工具调用记录。"""
        ctrl = DebugController()
        ctrl.snapshot_tool_call("tool_a", {"key": "val"})
        ctrl.snapshot_tool_call("tool_b", {"key": "val2"})
        assert len(ctrl._last_tool_calls) == 2
        ctrl.clear_tool_snapshots()
        assert len(ctrl._last_tool_calls) == 0


class TestStopWhenRunning:
    """运行中终止测试。"""

    @pytest.mark.asyncio
    async def test_stop_when_not_paused(self) -> None:
        """运行中调用 stop 直接设 FAILED。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        ctrl._state = DebugState.RUNNING
        await ctrl.stop()
        assert ctrl.state == DebugState.FAILED


class TestPauseContextDataclass:
    """PauseContext 数据类测试。"""

    def test_pause_context_defaults(self) -> None:
        """PauseContext 默认值。"""
        ctx = PauseContext(turn=1, agent_name="a", reason="test")
        assert ctx.turn == 1
        assert ctx.agent_name == "a"
        assert ctx.reason == "test"
        assert ctx.recent_messages == []
        assert ctx.last_llm_response is None
        assert ctx.last_tool_calls is None
        assert ctx.token_usage == {}
        assert ctx.metadata == {}
        assert ctx.paused_at  # 有值

    def test_pause_context_custom(self) -> None:
        """PauseContext 自定义值。"""
        ctx = PauseContext(
            turn=3, agent_name="b", reason="step_tool",
            recent_messages=[{"role": "user", "content": "hi"}],
            token_usage={"total_tokens": 100},
        )
        assert ctx.turn == 3
        assert len(ctx.recent_messages) == 1
        assert ctx.token_usage["total_tokens"] == 100


class TestDebugEnums:
    """枚举值测试。"""

    def test_debug_mode_values(self) -> None:
        """DebugMode 值。"""
        assert DebugMode.STEP_TURN.value == "step_turn"
        assert DebugMode.STEP_TOOL.value == "step_tool"
        assert DebugMode.CONTINUE.value == "continue"

    def test_debug_state_values(self) -> None:
        """DebugState 值。"""
        assert DebugState.IDLE.value == "idle"
        assert DebugState.RUNNING.value == "running"
        assert DebugState.PAUSED.value == "paused"
        assert DebugState.COMPLETED.value == "completed"
        assert DebugState.FAILED.value == "failed"
        assert DebugState.TIMEOUT.value == "timeout"

    def test_debug_event_type_values(self) -> None:
        """DebugEventType 值。"""
        assert DebugEventType.PAUSED.value == "paused"
        assert DebugEventType.RESUMED.value == "resumed"
        assert DebugEventType.STEP.value == "step"
        assert DebugEventType.COMPLETED.value == "completed"


class TestDictMessages:
    """dict 格式消息兼容测试。"""

    @pytest.mark.asyncio
    async def test_dict_messages_in_snapshot(self) -> None:
        """dict 格式消息也能正确快照。"""
        ctrl = DebugController(mode=DebugMode.STEP_TURN)
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]

        async def run_checkpoint() -> None:
            await ctrl.checkpoint(reason="turn_end", turn=1, agent_name="a", messages=msgs)

        task = asyncio.create_task(run_checkpoint())
        await asyncio.sleep(0.05)

        assert ctrl.pause_context is not None
        assert len(ctrl.pause_context.recent_messages) == 2
        assert ctrl.pause_context.recent_messages[0]["role"] == "user"

        await ctrl.step()
        await asyncio.sleep(0.05)
        await task
