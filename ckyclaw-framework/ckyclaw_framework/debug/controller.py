"""DebugController — Agent 执行调试控制器。

通过 RunConfig.debug_controller 注入。Runner 在关键位置调用 checkpoint()，
DebugController 决定是否暂停执行并等待用户操作。

核心设计原则：
- 不修改 Runner 的 Hook 语义（Hook 仍然非阻塞）
- checkpoint() 是显式的可阻塞调用
- 通过 asyncio.Event 实现暂停/恢复
- 暂停超时保护（默认 30 分钟）
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# 默认暂停超时（秒）
DEFAULT_PAUSE_TIMEOUT = 1800  # 30 分钟


class DebugStoppedError(Exception):
    """调试会话被用户终止或暂停超时时抛出。

    继承自 Exception（而非 BaseException），确保 Runner 的 except Exception 能正确捕获。
    """


class DebugMode(str, Enum):
    """调试模式。"""

    STEP_TURN = "step_turn"
    """每轮暂停 — LLM 回复后自动暂停。"""

    STEP_TOOL = "step_tool"
    """每次工具调用暂停 — 工具执行前自动暂停。"""

    CONTINUE = "continue"
    """连续运行 — 只在断点处暂停。"""


class DebugState(str, Enum):
    """调试会话状态。"""

    IDLE = "idle"
    """未开始。"""

    RUNNING = "running"
    """运行中。"""

    PAUSED = "paused"
    """已暂停，等待用户操作。"""

    COMPLETED = "completed"
    """执行完成。"""

    FAILED = "failed"
    """执行失败。"""

    TIMEOUT = "timeout"
    """暂停超时，自动终止。"""


class DebugEventType(str, Enum):
    """调试事件类型。"""

    PAUSED = "paused"
    """执行已暂停。"""

    RESUMED = "resumed"
    """执行已恢复。"""

    STEP = "step"
    """单步执行。"""

    LLM_START = "llm_start"
    """LLM 调用开始。"""

    LLM_END = "llm_end"
    """LLM 调用结束。"""

    TOOL_START = "tool_start"
    """工具调用开始。"""

    TOOL_END = "tool_end"
    """工具调用结束。"""

    HANDOFF = "handoff"
    """Agent 移交。"""

    COMPLETED = "completed"
    """执行完成。"""

    FAILED = "failed"
    """执行失败。"""

    TIMEOUT = "timeout"
    """暂停超时。"""


@dataclass
class PauseContext:
    """暂停时的上下文快照（轻量化，完整数据通过 API 按需获取）。"""

    turn: int
    """当前轮次。"""

    agent_name: str
    """当前 Agent 名称。"""

    reason: str
    """暂停原因（如 'step_turn', 'step_tool', 'breakpoint'）。"""

    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    """最近 5 条消息快照。"""

    last_llm_response: dict[str, Any] | None = None
    """最近 LLM 响应。"""

    last_tool_calls: list[dict[str, Any]] | None = None
    """最近工具调用结果。"""

    token_usage: dict[str, int] = field(default_factory=dict)
    """累计 Token 统计。"""

    paused_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """暂停时间戳（ISO 格式）。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """扩展元数据（如断点信息）。"""


@dataclass
class DebugEvent:
    """调试事件 — 推送给前端。"""

    type: DebugEventType
    """事件类型。"""

    data: dict[str, Any] = field(default_factory=dict)
    """事件数据。"""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """时间戳（ISO 格式）。"""


# 事件回调类型：async def callback(event: DebugEvent) -> None
EventCallback = Callable[[DebugEvent], Coroutine[Any, Any, None]]


class DebugController:
    """Agent 执行调试控制器。

    使用方式：
        controller = DebugController(mode=DebugMode.STEP_TURN)
        config = RunConfig(debug_controller=controller)
        result = await Runner.run(agent, input, config=config)

    Runner 在以下位置调用 controller.checkpoint()：
        1. 每轮 LLM 调用后（turn 级）
        2. 每次工具调用前（tool 级）
        3. 每次 Handoff 前（handoff 级）
    """

    def __init__(
        self,
        mode: DebugMode = DebugMode.STEP_TURN,
        pause_timeout: float = DEFAULT_PAUSE_TIMEOUT,
        on_event: EventCallback | None = None,
    ) -> None:
        """初始化调试控制器。

        Args:
            mode: 调试模式。
            pause_timeout: 暂停超时时间（秒），超时后自动终止。
            on_event: 事件回调（用于推送到 WebSocket 等）。
        """
        self._mode = mode
        self._pause_timeout = pause_timeout
        self._on_event = on_event
        self._state = DebugState.IDLE
        self._resume_event = asyncio.Event()
        self._pause_context: PauseContext | None = None
        self._pending_action: str | None = None  # "step" | "continue" | "stop"
        # LLM/Tool 快照（由 Runner 写入）
        self._last_llm_response: dict[str, Any] | None = None
        self._last_tool_calls: list[dict[str, Any]] = []
        self._messages_snapshot: list[dict[str, Any]] = []

    # === 属性 ===

    @property
    def mode(self) -> DebugMode:
        """当前调试模式。"""
        return self._mode

    @mode.setter
    def mode(self, value: DebugMode) -> None:
        """运行时切换调试模式。"""
        self._mode = value

    @property
    def state(self) -> DebugState:
        """当前调试状态。"""
        return self._state

    @property
    def pause_context(self) -> PauseContext | None:
        """当前暂停上下文（仅 PAUSED 状态有值）。"""
        return self._pause_context

    # === Runner 调用的检查点 ===

    async def checkpoint(
        self,
        *,
        reason: str,
        turn: int,
        agent_name: str,
        messages: list[Any],
        token_usage: dict[str, int] | None = None,
    ) -> None:
        """Runner 在关键位置调用此方法。

        根据 mode 决定是否暂停：
        - STEP_TURN 模式 + reason="turn_end" → 暂停
        - STEP_TOOL 模式 + reason="before_tool" → 暂停
        - CONTINUE 模式 → 不暂停（未来支持断点）
        - reason="before_handoff" → STEP_TURN 和 STEP_TOOL 都暂停

        Args:
            reason: 检查点原因（"turn_end" | "before_tool" | "before_handoff"）。
            turn: 当前轮次。
            agent_name: 当前 Agent 名称。
            messages: 当前消息列表。
            token_usage: 累计 Token 使用。
        """
        if self._state in (DebugState.COMPLETED, DebugState.FAILED, DebugState.TIMEOUT):
            return

        # 检查是否有待处理的 stop 操作（stop() 在 RUNNING 状态被调用）
        if self._pending_action == "stop":
            self._state = DebugState.FAILED
            self._pending_action = None
            raise DebugStoppedError("Debug session stopped by user")

        self._state = DebugState.RUNNING

        should_pause = False
        if reason == "turn_end" and self._mode in (DebugMode.STEP_TURN, DebugMode.STEP_TOOL):
            should_pause = True
        elif reason == "before_tool" and self._mode == DebugMode.STEP_TOOL:
            should_pause = True
        elif reason == "before_handoff" and self._mode in (DebugMode.STEP_TURN, DebugMode.STEP_TOOL):
            should_pause = True

        # step 操作后自动暂停（单步执行语义）
        if self._pending_action == "step":
            should_pause = True
            self._pending_action = None

        if not should_pause:
            return

        # 构建暂停上下文（轻量化：最近 5 条消息）
        recent = []
        for m in messages[-5:]:
            if hasattr(m, "role") and hasattr(m, "content"):
                recent.append({"role": str(m.role.value) if hasattr(m.role, "value") else str(m.role), "content": m.content})
            elif isinstance(m, dict):
                recent.append(m)

        self._pause_context = PauseContext(
            turn=turn,
            agent_name=agent_name,
            reason=reason,
            recent_messages=recent,
            last_llm_response=self._last_llm_response,
            last_tool_calls=self._last_tool_calls.copy() if self._last_tool_calls else None,
            token_usage=token_usage or {},
        )
        self._state = DebugState.PAUSED
        self._resume_event.clear()

        # 推送暂停事件
        await self._emit(DebugEvent(
            type=DebugEventType.PAUSED,
            data={"turn": turn, "agent_name": agent_name, "reason": reason},
        ))

        # 等待用户操作（带超时）
        try:
            await asyncio.wait_for(self._resume_event.wait(), timeout=self._pause_timeout)
        except asyncio.TimeoutError:
            self._state = DebugState.TIMEOUT
            await self._emit(DebugEvent(type=DebugEventType.TIMEOUT))
            raise DebugStoppedError("Debug session timed out") from None

        # 检查是否是 stop 操作
        if self._pending_action == "stop":
            self._state = DebugState.FAILED
            self._pending_action = None
            raise DebugStoppedError("Debug session stopped by user")

        self._state = DebugState.RUNNING
        self._pause_context = None

    # === 外部控制接口（API/WebSocket 调用） ===

    async def step(self) -> None:
        """单步执行 — 执行到下一个检查点后暂停。"""
        if self._state != DebugState.PAUSED:
            return
        self._pending_action = "step"
        await self._emit(DebugEvent(type=DebugEventType.STEP))
        self._resume_event.set()

    async def resume(self) -> None:
        """继续执行 — 运行到结束或下一个断点。"""
        if self._state != DebugState.PAUSED:
            return
        self._mode = DebugMode.CONTINUE
        self._pending_action = None
        await self._emit(DebugEvent(type=DebugEventType.RESUMED))
        self._resume_event.set()

    async def stop(self) -> None:
        """终止调试会话。"""
        self._pending_action = "stop"
        if self._state == DebugState.PAUSED:
            self._resume_event.set()
        # RUNNING 状态：设置 pending_action，下一次 checkpoint() 会检查并抛出异常

    def mark_completed(self) -> None:
        """Runner 执行完成时调用。"""
        self._state = DebugState.COMPLETED

    def mark_failed(self) -> None:
        """Runner 执行失败时调用。"""
        self._state = DebugState.FAILED

    # === 快照更新（Runner 调用） ===

    def snapshot_llm_response(self, response: dict[str, Any]) -> None:
        """记录最近 LLM 响应快照。"""
        self._last_llm_response = response

    def snapshot_tool_call(self, tool_name: str, arguments: dict[str, Any], result: str | None = None) -> None:
        """记录工具调用快照。"""
        entry: dict[str, Any] = {"tool_name": tool_name, "arguments": arguments}
        if result is not None:
            entry["result"] = result
        self._last_tool_calls.append(entry)

    def clear_tool_snapshots(self) -> None:
        """清除工具调用快照（每轮开始时调用）。"""
        self._last_tool_calls.clear()

    # === 内部方法 ===

    async def _emit(self, event: DebugEvent) -> None:
        """安全推送事件。"""
        if self._on_event is not None:
            try:
                await self._on_event(event)
            except Exception:
                logger.warning("Debug event callback failed for %s", event.type, exc_info=True)
