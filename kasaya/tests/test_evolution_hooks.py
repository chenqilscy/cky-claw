"""EvolutionHook 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from kasaya.evolution.hooks import EvolutionHook
from kasaya.evolution.signals import (
    SignalCollector,
    ToolPerformanceSignal,
)

# ── 辅助：最小化 RunContext 模拟 ──────────────────────────────


@dataclass
class _FakeAgent:
    name: str = "test-agent"


@dataclass
class _FakeRunContext:
    agent: _FakeAgent = field(default_factory=_FakeAgent)
    config: Any = None
    trace: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0


# ── 基础功能 ──────────────────────────────────────────────────


class TestEvolutionHookBasic:
    """EvolutionHook 基础行为测试。"""

    def test_init_creates_empty_collector_trackers(self) -> None:
        """初始化后内部追踪器为空。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        assert len(hook._tool_trackers) == 0
        assert hook._agent_name == ""

    def test_as_run_hooks_returns_hooks(self) -> None:
        """as_run_hooks 返回包含四个钩子的 RunHooks。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        run_hooks = hook.as_run_hooks()

        assert run_hooks.on_agent_start is not None
        assert run_hooks.on_tool_start is not None
        assert run_hooks.on_tool_end is not None
        assert run_hooks.on_error is not None
        # 未注册的钩子为 None
        assert run_hooks.on_run_start is None
        assert run_hooks.on_run_end is None
        assert run_hooks.on_llm_start is None
        assert run_hooks.on_llm_end is None
        assert run_hooks.on_handoff is None


# ── 工具信号采集 ────────────────────────────────────────────


class TestEvolutionHookToolSignal:
    """工具性能信号采集测试。"""

    @pytest.fixture()
    def setup(self) -> tuple[EvolutionHook, SignalCollector, _FakeRunContext]:
        """初始化钩子、采集器和上下文。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        ctx = _FakeRunContext()
        return hook, collector, ctx

    @pytest.mark.asyncio()
    async def test_tool_call_generates_success_signal(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """成功的工具调用生成 success 信号。"""
        hook, collector, ctx = setup
        await hook._on_agent_start(ctx, "my-agent")  # type: ignore[arg-type]
        await hook._on_tool_start(ctx, "search_tool", {"q": "hello"})  # type: ignore[arg-type]
        await hook._on_tool_end(ctx, "search_tool", "result")  # type: ignore[arg-type]

        signals = collector.signals
        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, ToolPerformanceSignal)
        assert sig.agent_name == "my-agent"
        assert sig.tool_name == "search_tool"
        assert sig.call_count == 1
        assert sig.success_count == 1
        assert sig.failure_count == 0
        assert sig.avg_duration_ms >= 0

    @pytest.mark.asyncio()
    async def test_multiple_tool_calls(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """多次工具调用生成多个信号。"""
        hook, collector, ctx = setup
        await hook._on_agent_start(ctx, "agent-a")  # type: ignore[arg-type]

        for i in range(3):
            await hook._on_tool_start(ctx, "tool_a", {"i": i})  # type: ignore[arg-type]
            await hook._on_tool_end(ctx, "tool_a", f"result-{i}")  # type: ignore[arg-type]

        assert len(collector.signals) == 3
        for sig in collector.signals:
            assert isinstance(sig, ToolPerformanceSignal)
            assert sig.tool_name == "tool_a"

    @pytest.mark.asyncio()
    async def test_different_tools(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """不同工具的调用分别生成信号。"""
        hook, collector, ctx = setup
        await hook._on_agent_start(ctx, "agent-a")  # type: ignore[arg-type]

        await hook._on_tool_start(ctx, "tool_a", {})  # type: ignore[arg-type]
        await hook._on_tool_end(ctx, "tool_a", "ok")  # type: ignore[arg-type]
        await hook._on_tool_start(ctx, "tool_b", {})  # type: ignore[arg-type]
        await hook._on_tool_end(ctx, "tool_b", "ok")  # type: ignore[arg-type]

        assert len(collector.signals) == 2
        names = {s.tool_name for s in collector.signals if isinstance(s, ToolPerformanceSignal)}
        assert names == {"tool_a", "tool_b"}

    @pytest.mark.asyncio()
    async def test_uses_ctx_agent_name_fallback(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """未调用 on_agent_start 时使用 ctx.agent.name 作为回退。"""
        hook, collector, ctx = setup
        # 不调用 on_agent_start
        await hook._on_tool_start(ctx, "tool_x", {})  # type: ignore[arg-type]
        await hook._on_tool_end(ctx, "tool_x", "ok")  # type: ignore[arg-type]

        sig = collector.signals[0]
        assert isinstance(sig, ToolPerformanceSignal)
        assert sig.agent_name == "test-agent"  # 来自 _FakeAgent.name

    @pytest.mark.asyncio()
    async def test_tool_end_without_start_is_noop(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """tool_end 没有对应的 tool_start 时不生成信号。"""
        hook, collector, ctx = setup
        await hook._on_tool_end(ctx, "orphan_tool", "result")  # type: ignore[arg-type]

        assert len(collector.signals) == 0


# ── 错误信号采集 ─────────────────────────────────────────────


class TestEvolutionHookError:
    """错误场景信号采集测试。"""

    @pytest.fixture()
    def setup(self) -> tuple[EvolutionHook, SignalCollector, _FakeRunContext]:
        """初始化。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        ctx = _FakeRunContext()
        return hook, collector, ctx

    @pytest.mark.asyncio()
    async def test_error_generates_failure_signal(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """on_error 在工具有未完成追踪时生成失败信号。"""
        hook, collector, ctx = setup
        await hook._on_agent_start(ctx, "err-agent")  # type: ignore[arg-type]
        await hook._on_tool_start(ctx, "bad_tool", {})  # type: ignore[arg-type]
        await hook._on_error(ctx, RuntimeError("boom"))  # type: ignore[arg-type]

        signals = collector.signals
        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, ToolPerformanceSignal)
        assert sig.failure_count == 1
        assert sig.success_count == 0
        assert sig.metadata.get("error") == "boom"

    @pytest.mark.asyncio()
    async def test_error_without_trackers_is_silent(
        self, setup: tuple[EvolutionHook, SignalCollector, _FakeRunContext]
    ) -> None:
        """没有活跃的工具追踪时，on_error 不生成信号。"""
        hook, collector, ctx = setup
        await hook._on_error(ctx, ValueError("no tool"))  # type: ignore[arg-type]
        assert len(collector.signals) == 0


# ── 信号聚合 ──────────────────────────────────────────────────


class TestEvolutionHookAggregation:
    """get_aggregated_signals 聚合逻辑测试。"""

    @pytest.mark.asyncio()
    async def test_aggregate_multiple_calls(self) -> None:
        """多次同工具调用聚合为单个信号。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        ctx = _FakeRunContext()

        await hook._on_agent_start(ctx, "agg-agent")  # type: ignore[arg-type]
        for _ in range(5):
            await hook._on_tool_start(ctx, "tool_x", {})  # type: ignore[arg-type]
            await hook._on_tool_end(ctx, "tool_x", "ok")  # type: ignore[arg-type]

        aggregated = hook.get_aggregated_signals()
        assert len(aggregated) == 1
        sig = aggregated[0]
        assert sig.call_count == 5
        assert sig.success_count == 5
        assert sig.failure_count == 0
        assert sig.avg_duration_ms >= 0

    @pytest.mark.asyncio()
    async def test_aggregate_different_tools(self) -> None:
        """不同工具分别聚合。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        ctx = _FakeRunContext()

        await hook._on_agent_start(ctx, "agg-agent")  # type: ignore[arg-type]
        for name in ("tool_a", "tool_b", "tool_a", "tool_b", "tool_b"):
            await hook._on_tool_start(ctx, name, {})  # type: ignore[arg-type]
            await hook._on_tool_end(ctx, name, "ok")  # type: ignore[arg-type]

        aggregated = hook.get_aggregated_signals()
        assert len(aggregated) == 2
        by_name = {s.tool_name: s for s in aggregated}
        assert by_name["tool_a"].call_count == 2
        assert by_name["tool_b"].call_count == 3

    def test_aggregate_empty(self) -> None:
        """空信号采集器返回空列表。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        assert hook.get_aggregated_signals() == []

    @pytest.mark.asyncio()
    async def test_aggregate_mixed_success_failure(self) -> None:
        """混合成功和失败调用正确聚合。"""
        collector = SignalCollector()
        hook = EvolutionHook(collector=collector)
        ctx = _FakeRunContext()

        await hook._on_agent_start(ctx, "mix-agent")  # type: ignore[arg-type]

        # 2 次成功
        for _ in range(2):
            await hook._on_tool_start(ctx, "unreliable_tool", {})  # type: ignore[arg-type]
            await hook._on_tool_end(ctx, "unreliable_tool", "ok")  # type: ignore[arg-type]

        # 1 次失败（通过 on_error）
        await hook._on_tool_start(ctx, "unreliable_tool", {})  # type: ignore[arg-type]
        await hook._on_error(ctx, RuntimeError("fail"))  # type: ignore[arg-type]

        aggregated = hook.get_aggregated_signals()
        assert len(aggregated) == 1
        sig = aggregated[0]
        assert sig.call_count == 3
        assert sig.success_count == 2
        assert sig.failure_count == 1
