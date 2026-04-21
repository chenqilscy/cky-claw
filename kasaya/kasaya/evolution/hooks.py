"""进化钩子 — 自动从 Runner 运行中采集进化信号。

EvolutionHook 实现 RunHooks 接口，在 Agent 运行过程中自动采集
工具性能信号（ToolPerformanceSignal），无需手动埋点。

用法::

    from kasaya.evolution import SignalCollector
    from kasaya.evolution.hooks import EvolutionHook

    collector = SignalCollector()
    hook = EvolutionHook(collector)
    config = RunConfig(hooks=hook.as_run_hooks())
    result = await Runner.run(agent, "Hello", config=config)
    # collector.signals 中已包含自动采集的信号
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kasaya.evolution.signals import (
    SignalCollector,
    SignalType,
    ToolPerformanceSignal,
)
from kasaya.runner.hooks import RunHooks

if TYPE_CHECKING:
    from kasaya.runner.run_context import RunContext


@dataclass
class _ToolCallTracker:
    """工具调用追踪器，记录调用开始时间和成功/失败状态。"""

    start_time_ns: int = 0
    success: bool = True
    error_msg: str = ""


@dataclass
class EvolutionHook:
    """自动信号采集钩子。

    通过 on_tool_start / on_tool_end / on_error 钩子自动采集
    ToolPerformanceSignal，将信号写入给定的 SignalCollector。

    Attributes:
        collector: 信号采集器实例，采集到的信号会追加到此处。
    """

    collector: SignalCollector
    """信号采集器，所有自动采集的信号都写入此实例。"""

    _tool_trackers: dict[str, list[_ToolCallTracker]] = field(
        default_factory=dict, repr=False
    )
    """工具调用追踪器。key = tool_name, value = 调用列表。"""

    _agent_name: str = field(default="", repr=False)
    """当前运行的 Agent 名称。"""

    async def _on_agent_start(self, ctx: RunContext, agent_name: str) -> None:
        """记录当前 Agent 名称。"""
        self._agent_name = agent_name

    async def _on_tool_start(
        self, ctx: RunContext, tool_name: str, arguments: dict[str, Any]
    ) -> None:
        """记录工具调用开始时间。"""
        tracker = _ToolCallTracker(start_time_ns=time.monotonic_ns())
        self._tool_trackers.setdefault(tool_name, []).append(tracker)

    async def _on_tool_end(
        self, ctx: RunContext, tool_name: str, result: str
    ) -> None:
        """记录工具调用结果并生成信号。"""
        trackers = self._tool_trackers.get(tool_name)
        if not trackers:
            return
        tracker = trackers[-1]
        duration_ns = time.monotonic_ns() - tracker.start_time_ns
        duration_ms = duration_ns / 1_000_000

        agent_name = self._agent_name or ctx.agent.name
        self.collector.add_signal(
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name=agent_name,
                tool_name=tool_name,
                call_count=1,
                success_count=1,
                failure_count=0,
                avg_duration_ms=duration_ms,
            )
        )

    async def _on_error(self, ctx: RunContext, error: Exception) -> None:
        """工具调用异常时标记最近一次调用为失败。"""
        # 为每个有未完成追踪器的工具记录失败信号
        for tool_name, trackers in self._tool_trackers.items():
            if trackers and trackers[-1].success:
                tracker = trackers[-1]
                tracker.success = False
                tracker.error_msg = str(error)
                duration_ns = time.monotonic_ns() - tracker.start_time_ns
                duration_ms = duration_ns / 1_000_000
                agent_name = self._agent_name or ctx.agent.name
                self.collector.add_signal(
                    ToolPerformanceSignal(
                        signal_type=SignalType.TOOL_PERFORMANCE,
                        agent_name=agent_name,
                        tool_name=tool_name,
                        call_count=1,
                        success_count=0,
                        failure_count=1,
                        avg_duration_ms=duration_ms,
                        metadata={"error": tracker.error_msg},
                    )
                )

    def as_run_hooks(self) -> RunHooks:
        """转换为 RunHooks 实例，可直接传入 RunConfig。

        Returns:
            RunHooks 实例，包含自动信号采集的钩子函数。
        """
        return RunHooks(
            on_agent_start=self._on_agent_start,
            on_tool_start=self._on_tool_start,
            on_tool_end=self._on_tool_end,
            on_error=self._on_error,
        )

    def get_aggregated_signals(self) -> list[ToolPerformanceSignal]:
        """获取按工具名聚合的性能信号。

        将 collector 中的所有 ToolPerformanceSignal 按 tool_name 聚合，
        返回每个工具的汇总信号。

        Returns:
            聚合后的工具性能信号列表。
        """
        from kasaya.evolution.signals import SignalType

        tool_stats: dict[str, dict[str, Any]] = {}
        for signal in self.collector.get_signals_by_type(SignalType.TOOL_PERFORMANCE):
            if not isinstance(signal, ToolPerformanceSignal):
                continue
            key = f"{signal.agent_name}:{signal.tool_name}"
            if key not in tool_stats:
                tool_stats[key] = {
                    "agent_name": signal.agent_name,
                    "tool_name": signal.tool_name,
                    "call_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "total_duration_ms": 0.0,
                }
            stats = tool_stats[key]
            stats["call_count"] += signal.call_count
            stats["success_count"] += signal.success_count
            stats["failure_count"] += signal.failure_count
            stats["total_duration_ms"] += signal.avg_duration_ms * signal.call_count

        result: list[ToolPerformanceSignal] = []
        for stats in tool_stats.values():
            cc = stats["call_count"]
            avg_ms = stats["total_duration_ms"] / cc if cc > 0 else 0.0
            result.append(
                ToolPerformanceSignal(
                    signal_type=SignalType.TOOL_PERFORMANCE,
                    agent_name=stats["agent_name"],
                    tool_name=stats["tool_name"],
                    call_count=cc,
                    success_count=stats["success_count"],
                    failure_count=stats["failure_count"],
                    avg_duration_ms=avg_ms,
                )
            )
        return result
