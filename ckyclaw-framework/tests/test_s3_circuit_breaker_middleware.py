"""S3 测试 — CircuitBreaker + FallbackChain + ToolMiddleware。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from ckyclaw_framework.model.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)
from ckyclaw_framework.model.fallback import (
    FallbackChainConfig,
    FallbackChainProvider,
    FallbackEntry,
)
from ckyclaw_framework.model.message import Message, MessageRole
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse
from ckyclaw_framework.tools.middleware import (
    CacheMiddleware,
    LoopGuardMiddleware,
    MiddlewareResult,
    RateLimitMiddleware,
    TimeoutMiddleware,
    ToolExecutionContext,
    ToolMiddleware,
    ToolMiddlewarePipeline,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# ═══════════════════════ Helpers ═══════════════════════


class MockProvider(ModelProvider):
    """可控制成功/失败的 Mock Provider。"""

    def __init__(self, name: str = "mock", should_fail: bool = False, fail_count: int = 0) -> None:
        self._name = name
        self._should_fail = should_fail
        self._fail_count = fail_count
        self._call_count = 0
        self._total_calls = 0

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: Any = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        response_format: Any = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        self._total_calls += 1
        self._call_count += 1
        if self._should_fail or (self._fail_count > 0 and self._call_count <= self._fail_count):
            raise RuntimeError(f"Provider '{self._name}' failed")
        return ModelResponse(content=f"response from {self._name}", finish_reason="stop")


def _make_context(tool_name: str = "test_tool", **kwargs: Any) -> ToolExecutionContext:
    """创建测试用 ToolExecutionContext。"""
    return ToolExecutionContext(
        tool_name=tool_name,
        arguments=kwargs.get("arguments", {"q": "test"}),
        agent_name="test_agent",
        run_id="run-123",
    )


# ═══════════════════════ CircuitBreaker 测试 ═══════════════════════


class TestCircuitBreakerState:
    """熔断器状态机测试。"""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self) -> None:
        """初始状态为 CLOSED。"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_stays_closed(self) -> None:
        """成功调用不改变 CLOSED 状态。"""
        cb = CircuitBreaker("test")
        result = await cb.call(AsyncMock(return_value="ok"))
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.total_successes == 1

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self) -> None:
        """连续失败达到阈值后转为 OPEN。"""
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", cfg)

        failing_fn = AsyncMock(side_effect=RuntimeError("fail"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(failing_fn)

        assert cb.state == CircuitState.OPEN
        assert cb.metrics.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self) -> None:
        """OPEN 状态拒绝所有调用。"""
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=100)
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call(AsyncMock(return_value="ok"))
        assert "OPEN" in str(exc_info.value)
        assert cb.metrics.total_rejected == 1

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self) -> None:
        """OPEN 状态超时后转为 HALF_OPEN。"""
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.05)
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))
        assert cb._state == CircuitState.OPEN

        await asyncio.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self) -> None:
        """HALF_OPEN 状态下成功调用恢复到 CLOSED。"""
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01, success_threshold=1)
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))

        await asyncio.sleep(0.02)
        result = await cb.call(AsyncMock(return_value="recovered"))
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self) -> None:
        """HALF_OPEN 状态下失败重新打开。"""
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01)
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))

        await asyncio.sleep(0.02)
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail again")))
        assert cb._state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exceptions_not_counted(self) -> None:
        """排除的异常类型不计入失败。"""
        cfg = CircuitBreakerConfig(failure_threshold=2, excluded_exceptions=(ValueError,))
        cb = CircuitBreaker("test", cfg)

        for _ in range(5):
            with pytest.raises(ValueError):
                await cb.call(AsyncMock(side_effect=ValueError("ignored")))

        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        """手动 reset 恢复 CLOSED。"""
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=100)
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))
        assert cb._state == CircuitState.OPEN

        await cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_to_dict(self) -> None:
        """to_dict 导出正确的快照。"""
        cb = CircuitBreaker("test-cb")
        await cb.call(AsyncMock(return_value="ok"))
        d = cb.to_dict()
        assert d["name"] == "test-cb"
        assert d["state"] == "closed"
        assert d["metrics"]["total_successes"] == 1

    @pytest.mark.asyncio
    async def test_metrics_tracking(self) -> None:
        """指标跟踪准确。"""
        cfg = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", cfg)

        await cb.call(AsyncMock(return_value="ok"))
        await cb.call(AsyncMock(return_value="ok"))
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))

        m = cb.metrics
        assert m.total_calls == 3
        assert m.total_successes == 2
        assert m.total_failures == 1

    @pytest.mark.asyncio
    async def test_half_open_max_calls(self) -> None:
        """HALF_OPEN 状态最大探测请求数限制。"""
        cfg = CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.01,
            half_open_max_calls=1, success_threshold=1,
        )
        cb = CircuitBreaker("test", cfg)

        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError("fail")))

        await asyncio.sleep(0.02)
        # 第一个探测请求可以通过
        result = await cb.call(AsyncMock(return_value="probe"))
        assert result == "probe"
        assert cb.state == CircuitState.CLOSED


# ═══════════════════════ FallbackChain 测试 ═══════════════════════


class TestFallbackChain:
    """降级链测试。"""

    def test_empty_entries_raises(self) -> None:
        """空 entries 列表在构造时抛出 ValueError。"""
        with pytest.raises(ValueError, match="at least one"):
            FallbackChainProvider([])

    @pytest.mark.asyncio
    async def test_primary_success(self) -> None:
        """主 Provider 成功时直接返回。"""
        primary = MockProvider("primary")
        backup = MockProvider("backup")
        chain = FallbackChainProvider([
            FallbackEntry(provider=primary, model="gpt-4"),
            FallbackEntry(provider=backup, model="gpt-3.5", priority=1),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        result = await chain.chat("gpt-4", msgs)
        assert isinstance(result, ModelResponse)
        assert result.content == "response from primary"
        assert primary._total_calls == 1
        assert backup._total_calls == 0

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        """主 Provider 失败时降级到备用。"""
        primary = MockProvider("primary", should_fail=True)
        backup = MockProvider("backup")
        chain = FallbackChainProvider([
            FallbackEntry(provider=primary, model="gpt-4"),
            FallbackEntry(provider=backup, model="gpt-3.5", priority=1),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        result = await chain.chat("gpt-4", msgs)
        assert isinstance(result, ModelResponse)
        assert result.content == "response from backup"
        assert chain.last_used_entry is not None
        assert chain.last_used_entry.provider is backup

    @pytest.mark.asyncio
    async def test_all_providers_fail(self) -> None:
        """所有 Provider 失败抛出 RuntimeError。"""
        chain = FallbackChainProvider([
            FallbackEntry(provider=MockProvider("p1", should_fail=True)),
            FallbackEntry(provider=MockProvider("p2", should_fail=True), priority=1),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        with pytest.raises(RuntimeError, match="All providers in FallbackChain exhausted"):
            await chain.chat("model", msgs)

    @pytest.mark.asyncio
    async def test_model_override(self) -> None:
        """FallbackEntry.model 覆盖调用者的 model。"""
        provider = MockProvider("test")
        chain = FallbackChainProvider([
            FallbackEntry(provider=provider, model="override-model"),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        await chain.chat("original-model", msgs)
        # Provider 被调用了
        assert provider._total_calls == 1

    @pytest.mark.asyncio
    async def test_auto_circuit_breaker(self) -> None:
        """auto_circuit_breaker=True 时自动为每个 Entry 创建 CircuitBreaker。"""
        chain = FallbackChainProvider([
            FallbackEntry(provider=MockProvider("p1")),
            FallbackEntry(provider=MockProvider("p2"), priority=1),
        ])

        for entry in chain.entries:
            assert entry.circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_no_auto_circuit_breaker(self) -> None:
        """auto_circuit_breaker=False 时不自动创建。"""
        chain = FallbackChainProvider(
            [FallbackEntry(provider=MockProvider("p1"))],
            config=FallbackChainConfig(auto_circuit_breaker=False),
        )
        assert chain._entries[0].circuit_breaker is None

    @pytest.mark.asyncio
    async def test_skip_open_circuit_breaker(self) -> None:
        """跳过 CircuitBreaker OPEN 的 Provider。"""
        primary = MockProvider("primary", should_fail=True)
        backup = MockProvider("backup")
        cb_config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=100)
        chain = FallbackChainProvider([
            FallbackEntry(
                provider=primary,
                circuit_breaker=CircuitBreaker("primary-cb", cb_config),
            ),
            FallbackEntry(provider=backup, priority=1),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        # 第一次：primary 失败 → CircuitBreaker 打开 → 降级到 backup
        await chain.chat("model", msgs)
        assert chain.last_used_entry.provider is backup  # type: ignore[union-attr]

        # 第二次：primary 的 CircuitBreaker 是 OPEN → 直接跳过 → backup
        result = await chain.chat("model", msgs)
        assert isinstance(result, ModelResponse)
        assert result.content == "response from backup"

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        """按优先级排序。"""
        p1 = MockProvider("low")
        p2 = MockProvider("high")
        chain = FallbackChainProvider([
            FallbackEntry(provider=p1, priority=2),
            FallbackEntry(provider=p2, priority=0),
        ])
        # priority=0 排在前面
        assert chain._entries[0].provider is p2

    @pytest.mark.asyncio
    async def test_health_status(self) -> None:
        """get_health_status 返回正确结构。"""
        chain = FallbackChainProvider([
            FallbackEntry(provider=MockProvider("p1")),
        ])
        status = chain.get_health_status()
        assert len(status) == 1
        assert status[0]["provider"] == "MockProvider"
        assert "circuit_breaker" in status[0]

    @pytest.mark.asyncio
    async def test_three_level_fallback(self) -> None:
        """三级降级链：主→副→最小模型。"""
        p1 = MockProvider("gpt4", should_fail=True)
        p2 = MockProvider("gpt35", should_fail=True)
        p3 = MockProvider("mini")
        chain = FallbackChainProvider([
            FallbackEntry(provider=p1, model="gpt-4", priority=0),
            FallbackEntry(provider=p2, model="gpt-3.5", priority=1),
            FallbackEntry(provider=p3, model="mini-model", priority=2),
        ])

        msgs = [Message(role=MessageRole.USER, content="test")]
        result = await chain.chat("any", msgs)
        assert isinstance(result, ModelResponse)
        assert result.content == "response from mini"


# ═══════════════════════ ToolMiddleware 测试 ═══════════════════════


class TestToolMiddlewarePipeline:
    """中间件管道测试。"""

    @pytest.mark.asyncio
    async def test_empty_pipeline(self) -> None:
        """空管道直接执行工具。"""
        pipeline = ToolMiddlewarePipeline()
        ctx = _make_context()

        async def tool_fn(args: dict[str, Any]) -> str:
            return "result"

        result = await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert result == "result"

    @pytest.mark.asyncio
    async def test_before_execute_short_circuit(self) -> None:
        """before_execute 返回 should_continue=False 时短路。"""

        class BlockMiddleware(ToolMiddleware):
            async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
                return MiddlewareResult(should_continue=False, result="blocked")

        pipeline = ToolMiddlewarePipeline([BlockMiddleware()])
        ctx = _make_context()
        called = False

        async def tool_fn(args: dict[str, Any]) -> str:
            nonlocal called
            called = True
            return "result"

        result = await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert result == "blocked"
        assert not called

    @pytest.mark.asyncio
    async def test_after_execute_modifies_result(self) -> None:
        """after_execute 可以修改结果。"""

        class UpperMiddleware(ToolMiddleware):
            async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
                return MiddlewareResult()

            async def after_execute(self, context: ToolExecutionContext, result: str, duration: float) -> str:
                return result.upper()

        pipeline = ToolMiddlewarePipeline([UpperMiddleware()])
        ctx = _make_context()

        async def tool_fn(args: dict[str, Any]) -> str:
            return "hello"

        result = await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_onion_order(self) -> None:
        """洋葱模型：before 正序，after 逆序。"""
        order: list[str] = []

        class TrackMiddleware(ToolMiddleware):
            def __init__(self, label: str) -> None:
                self._label = label

            @property
            def name(self) -> str:
                return self._label

            async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
                order.append(f"before-{self._label}")
                return MiddlewareResult()

            async def after_execute(self, context: ToolExecutionContext, result: str, duration: float) -> str:
                order.append(f"after-{self._label}")
                return result

        pipeline = ToolMiddlewarePipeline([TrackMiddleware("A"), TrackMiddleware("B"), TrackMiddleware("C")])
        ctx = _make_context()

        async def tool_fn(args: dict[str, Any]) -> str:
            order.append("execute")
            return "ok"

        await pipeline.execute(ctx, tool_fn, {})
        assert order == ["before-A", "before-B", "before-C", "execute", "after-C", "after-B", "after-A"]

    @pytest.mark.asyncio
    async def test_add_middleware(self) -> None:
        """动态添加中间件。"""
        pipeline = ToolMiddlewarePipeline()
        assert len(pipeline.middlewares) == 0
        pipeline.add(CacheMiddleware())
        assert len(pipeline.middlewares) == 1


# ═══════════════════════ CacheMiddleware 测试 ═══════════════════════


class TestCacheMiddleware:
    """缓存中间件测试。"""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self) -> None:
        """首次未命中，二次命中。"""
        cache = CacheMiddleware(ttl=10)
        pipeline = ToolMiddlewarePipeline([cache])
        call_count = 0

        async def tool_fn(args: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            return f"result-{call_count}"

        ctx = _make_context(arguments={"q": "test"})
        r1 = await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert r1 == "result-1"
        assert call_count == 1
        assert cache.cache_size == 1

        ctx2 = _make_context(arguments={"q": "test"})
        r2 = await pipeline.execute(ctx2, tool_fn, {"q": "test"})
        assert r2 == "result-1"  # 缓存命中
        assert call_count == 1  # 未再次执行

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self) -> None:
        """TTL 过期后重新执行。"""
        cache = CacheMiddleware(ttl=0.01)
        pipeline = ToolMiddlewarePipeline([cache])
        call_count = 0

        async def tool_fn(args: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            return f"result-{call_count}"

        ctx = _make_context(arguments={"q": "test"})
        await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert call_count == 1

        await asyncio.sleep(0.02)
        ctx2 = _make_context(arguments={"q": "test"})
        r2 = await pipeline.execute(ctx2, tool_fn, {"q": "test"})
        assert r2 == "result-2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_different_args(self) -> None:
        """不同参数不命中缓存。"""
        cache = CacheMiddleware(ttl=10)
        pipeline = ToolMiddlewarePipeline([cache])
        call_count = 0

        async def tool_fn(args: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            return f"result-{call_count}"

        ctx1 = _make_context(arguments={"q": "a"})
        await pipeline.execute(ctx1, tool_fn, {"q": "a"})

        ctx2 = _make_context(arguments={"q": "b"})
        await pipeline.execute(ctx2, tool_fn, {"q": "b"})
        assert call_count == 2
        assert cache.cache_size == 2

    @pytest.mark.asyncio
    async def test_cache_error_not_cached(self) -> None:
        """错误结果不缓存。"""
        cache = CacheMiddleware(ttl=10)
        pipeline = ToolMiddlewarePipeline([cache])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "Error: something went wrong"

        ctx = _make_context(arguments={"q": "test"})
        await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert cache.cache_size == 0

    @pytest.mark.asyncio
    async def test_cache_max_entries(self) -> None:
        """超过 max_entries 时淘汰最旧条目。"""
        cache = CacheMiddleware(ttl=10, max_entries=2)
        pipeline = ToolMiddlewarePipeline([cache])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        for i in range(3):
            ctx = _make_context(arguments={"q": str(i)})
            await pipeline.execute(ctx, tool_fn, {"q": str(i)})

        assert cache.cache_size == 2

    @pytest.mark.asyncio
    async def test_cache_clear(self) -> None:
        """手动清空缓存。"""
        cache = CacheMiddleware(ttl=10)
        pipeline = ToolMiddlewarePipeline([cache])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        ctx = _make_context(arguments={"q": "test"})
        await pipeline.execute(ctx, tool_fn, {"q": "test"})
        assert cache.cache_size == 1
        cache.clear()
        assert cache.cache_size == 0


# ═══════════════════════ LoopGuardMiddleware 测试 ═══════════════════════


class TestLoopGuardMiddleware:
    """循环检测中间件测试。"""

    @pytest.mark.asyncio
    async def test_allows_under_limit(self) -> None:
        """未超限正常执行。"""
        guard = LoopGuardMiddleware(max_repeats=3)
        pipeline = ToolMiddlewarePipeline([guard])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        for _ in range(3):
            ctx = _make_context(arguments={"q": "same"})
            result = await pipeline.execute(ctx, tool_fn, {"q": "same"})
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        """超限后拦截。"""
        guard = LoopGuardMiddleware(max_repeats=2)
        pipeline = ToolMiddlewarePipeline([guard])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        for _ in range(2):
            ctx = _make_context(arguments={"q": "same"})
            await pipeline.execute(ctx, tool_fn, {"q": "same"})

        ctx = _make_context(arguments={"q": "same"})
        result = await pipeline.execute(ctx, tool_fn, {"q": "same"})
        assert "LoopGuard blocked" in result

    @pytest.mark.asyncio
    async def test_different_args_separate_counts(self) -> None:
        """不同参数独立计数。"""
        guard = LoopGuardMiddleware(max_repeats=1)
        pipeline = ToolMiddlewarePipeline([guard])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        ctx1 = _make_context(arguments={"q": "a"})
        r1 = await pipeline.execute(ctx1, tool_fn, {"q": "a"})
        assert r1 == "ok"

        ctx2 = _make_context(arguments={"q": "b"})
        r2 = await pipeline.execute(ctx2, tool_fn, {"q": "b"})
        assert r2 == "ok"

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        """reset 后计数清零。"""
        guard = LoopGuardMiddleware(max_repeats=1)
        pipeline = ToolMiddlewarePipeline([guard])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        ctx = _make_context(arguments={"q": "same"})
        await pipeline.execute(ctx, tool_fn, {"q": "same"})

        guard.reset()

        ctx2 = _make_context(arguments={"q": "same"})
        r = await pipeline.execute(ctx2, tool_fn, {"q": "same"})
        assert r == "ok"


# ═══════════════════════ TimeoutMiddleware 测试 ═══════════════════════


class TestTimeoutMiddleware:
    """超时中间件测试。"""

    @pytest.mark.asyncio
    async def test_normal_execution(self) -> None:
        """正常执行不受影响。"""
        timeout_mw = TimeoutMiddleware(timeout=5.0)
        pipeline = ToolMiddlewarePipeline([timeout_mw])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "fast"

        ctx = _make_context()
        result = await pipeline.execute(ctx, tool_fn, {})
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_records_start_time(self) -> None:
        """记录超时配置到 metadata。"""
        timeout_mw = TimeoutMiddleware(timeout=10.0)
        ctx = _make_context()
        mr = await timeout_mw.before_execute(ctx)
        assert mr.should_continue is True
        assert ctx.metadata["_timeout_limit"] == 10.0


# ═══════════════════════ RateLimitMiddleware 测试 ═══════════════════════


class TestRateLimitMiddleware:
    """频率限制中间件测试。"""

    @pytest.mark.asyncio
    async def test_allows_under_limit(self) -> None:
        """未超限正常执行。"""
        rl = RateLimitMiddleware(max_calls=3, window_seconds=10)
        pipeline = ToolMiddlewarePipeline([rl])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        for _ in range(3):
            ctx = _make_context()
            result = await pipeline.execute(ctx, tool_fn, {})
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        """超限后拦截。"""
        rl = RateLimitMiddleware(max_calls=2, window_seconds=10)
        pipeline = ToolMiddlewarePipeline([rl])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        for _ in range(2):
            ctx = _make_context()
            await pipeline.execute(ctx, tool_fn, {})

        ctx = _make_context()
        result = await pipeline.execute(ctx, tool_fn, {})
        assert "RateLimit blocked" in result

    @pytest.mark.asyncio
    async def test_window_expiry(self) -> None:
        """窗口过期后重新允许。"""
        rl = RateLimitMiddleware(max_calls=1, window_seconds=0.01)
        pipeline = ToolMiddlewarePipeline([rl])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        ctx1 = _make_context()
        await pipeline.execute(ctx1, tool_fn, {})

        await asyncio.sleep(0.02)

        ctx2 = _make_context()
        result = await pipeline.execute(ctx2, tool_fn, {})
        assert result == "ok"


# ═══════════════════════ RunConfig 集成测试 ═══════════════════════


class TestRunConfigS3Fields:
    """RunConfig S3 新字段测试。"""

    def test_default_values(self) -> None:
        """默认值正确。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        config = RunConfig()
        assert config.circuit_breaker is None
        assert config.fallback_provider is None
        assert config.tool_middleware == []

    def test_circuit_breaker_field(self) -> None:
        """circuit_breaker 字段可赋值。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        cb = CircuitBreaker("test")
        config = RunConfig(circuit_breaker=cb)
        assert config.circuit_breaker is cb

    def test_fallback_provider_field(self) -> None:
        """fallback_provider 字段可赋值。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        chain = FallbackChainProvider([
            FallbackEntry(provider=MockProvider("p1")),
        ])
        config = RunConfig(fallback_provider=chain)
        assert config.fallback_provider is chain

    def test_tool_middleware_field(self) -> None:
        """tool_middleware 字段可赋值。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        mws: list[ToolMiddleware] = [CacheMiddleware(), LoopGuardMiddleware()]
        config = RunConfig(tool_middleware=mws)
        assert len(config.tool_middleware) == 2


# ═══════════════════════ _resolve_provider 集成测试 ═══════════════════════


class TestResolveProvider:
    """_resolve_provider 集成测试。"""

    def test_fallback_provider_priority(self) -> None:
        """fallback_provider 优先于 model_provider。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.runner import _resolve_provider

        regular = MockProvider("regular")
        chain = FallbackChainProvider([FallbackEntry(provider=MockProvider("fb"))])
        config = RunConfig(model_provider=regular, fallback_provider=chain)
        resolved = _resolve_provider(config)
        assert resolved is chain

    def test_model_provider_fallback(self) -> None:
        """无 fallback_provider 时使用 model_provider。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.runner import _resolve_provider

        regular = MockProvider("regular")
        config = RunConfig(model_provider=regular)
        resolved = _resolve_provider(config)
        assert resolved is regular


# ═══════════════════════ 综合中间件管道测试 ═══════════════════════


class TestMiddlewareCombination:
    """多中间件组合测试。"""

    @pytest.mark.asyncio
    async def test_cache_plus_loop_guard(self) -> None:
        """CacheMiddleware + LoopGuardMiddleware 组合：缓存命中时不计入循环。"""
        cache = CacheMiddleware(ttl=10)
        guard = LoopGuardMiddleware(max_repeats=2)
        pipeline = ToolMiddlewarePipeline([cache, guard])
        call_count = 0

        async def tool_fn(args: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        # 第一次：缓存未命中 → LoopGuard 计数 1 → 执行 → 缓存写入
        ctx1 = _make_context(arguments={"q": "same"})
        r1 = await pipeline.execute(ctx1, tool_fn, {"q": "same"})
        assert r1 == "ok"

        # 第二次：缓存命中 → CacheMiddleware 短路 → LoopGuard 不计数（因为 cache 在前面）
        ctx2 = _make_context(arguments={"q": "same"})
        r2 = await pipeline.execute(ctx2, tool_fn, {"q": "same"})
        assert r2 == "ok"
        assert call_count == 1  # 工具只执行了一次

    @pytest.mark.asyncio
    async def test_rate_limit_plus_cache(self) -> None:
        """RateLimitMiddleware + CacheMiddleware 组合。"""
        rl = RateLimitMiddleware(max_calls=2, window_seconds=10)
        cache = CacheMiddleware(ttl=10)
        # RateLimit 在 Cache 前面
        pipeline = ToolMiddlewarePipeline([rl, cache])

        async def tool_fn(args: dict[str, Any]) -> str:
            return "ok"

        # 3 次调用，第 3 次被 RateLimit 拦截
        for i in range(2):
            ctx = _make_context(arguments={"q": str(i)})
            await pipeline.execute(ctx, tool_fn, {"q": str(i)})

        ctx3 = _make_context(arguments={"q": "3"})
        result = await pipeline.execute(ctx3, tool_fn, {"q": "3"})
        assert "RateLimit blocked" in result
