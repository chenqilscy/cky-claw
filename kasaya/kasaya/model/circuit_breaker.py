"""CircuitBreaker — LLM 调用熔断器。

三种状态：
- CLOSED：正常通行，记录失败计数
- OPEN：拒绝所有请求，等待恢复超时后转入 HALF_OPEN
- HALF_OPEN：放行一个探测请求，成功则恢复 CLOSED，失败则回到 OPEN

参考 Resilience4j / Polly 的经典实现。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """熔断器状态。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """熔断器配置。"""

    failure_threshold: int = 5
    """连续失败 N 次后打开熔断器。"""

    recovery_timeout: float = 30.0
    """OPEN 状态持续秒数后转入 HALF_OPEN。"""

    half_open_max_calls: int = 1
    """HALF_OPEN 状态允许的最大探测请求数。"""

    success_threshold: int = 1
    """HALF_OPEN 状态连续成功 N 次后恢复 CLOSED。"""

    excluded_exceptions: tuple[type[BaseException], ...] = ()
    """不计入失败的异常类型（如参数校验错误）。"""


@dataclass
class CircuitBreakerMetrics:
    """熔断器运行时指标。"""

    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: float | None = None
    last_state_change_time: float = field(default_factory=time.monotonic)
    state_changes: list[dict[str, Any]] = field(default_factory=list)


class CircuitBreakerOpenError(Exception):
    """熔断器处于 OPEN 状态时抛出。"""

    def __init__(self, provider_name: str, remaining_seconds: float) -> None:
        self.provider_name = provider_name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker for '{provider_name}' is OPEN, "
            f"retry in {remaining_seconds:.1f}s"
        )


class CircuitBreaker:
    """通用熔断器，包装异步调用。

    用法::

        cb = CircuitBreaker("openai-gpt4", CircuitBreakerConfig(failure_threshold=3))
        try:
            result = await cb.call(provider.chat, model=..., messages=...)
        except CircuitBreakerOpenError:
            # 触发 FallbackChain
            ...
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """当前状态（自动检测 OPEN → HALF_OPEN 超时转换）。"""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._metrics.last_state_change_time
            if elapsed >= self.config.recovery_timeout:
                # 延迟转换，在 call() 中用锁保护
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """运行时指标（只读快照）。"""
        return self._metrics

    async def call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """通过熔断器执行异步调用。

        Args:
            fn: 异步可调用对象
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            fn 的返回值

        Raises:
            CircuitBreakerOpenError: 熔断器开启时
        """
        async with self._lock:
            current_state = self._check_state_transition()

            if current_state == CircuitState.OPEN:
                self._metrics.total_rejected += 1
                remaining = self.config.recovery_timeout - (
                    time.monotonic() - self._metrics.last_state_change_time
                )
                raise CircuitBreakerOpenError(self.name, max(0.0, remaining))

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._metrics.total_rejected += 1
                    raise CircuitBreakerOpenError(self.name, 0.0)
                self._half_open_calls += 1

        # 在锁外执行实际调用
        try:
            result = await fn(*args, **kwargs)
        except Exception as e:
            if isinstance(e, self.config.excluded_exceptions):
                async with self._lock:
                    self._metrics.total_calls += 1
                raise
            await self._on_failure(e)
            raise
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        """记录成功。"""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_successes += 1
            self._metrics.consecutive_failures = 0
            self._metrics.consecutive_successes += 1

            if self._state == CircuitState.HALF_OPEN and self._metrics.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    async def _on_failure(self, error: Exception) -> None:
        """记录失败。"""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_failures += 1
            self._metrics.consecutive_failures += 1
            self._metrics.consecutive_successes = 0
            self._metrics.last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN or (
                self._state == CircuitState.CLOSED
                and self._metrics.consecutive_failures >= self.config.failure_threshold
            ):
                self._transition_to(CircuitState.OPEN)

    def _check_state_transition(self) -> CircuitState:
        """检查并执行 OPEN → HALF_OPEN 的超时转换。"""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._metrics.last_state_change_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转移（必须在锁内调用）。"""
        old_state = self._state
        self._state = new_state
        now = time.monotonic()
        self._metrics.last_state_change_time = now
        self._metrics.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "time": now,
        })
        # 限制 state_changes 历史长度，防止长期运行内存泄漏
        if len(self._metrics.state_changes) > 100:
            self._metrics.state_changes = self._metrics.state_changes[-50:]

        if new_state == CircuitState.CLOSED:
            self._metrics.consecutive_failures = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._metrics.consecutive_successes = 0

        logger.info(
            "CircuitBreaker '%s': %s → %s",
            self.name, old_state.value, new_state.value,
        )

    async def reset(self) -> None:
        """手动重置到 CLOSED 状态。"""
        async with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._metrics.consecutive_failures = 0
            self._metrics.consecutive_successes = 0

    def to_dict(self) -> dict[str, Any]:
        """导出状态快照（用于 APM Dashboard）。"""
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": {
                "total_calls": self._metrics.total_calls,
                "total_failures": self._metrics.total_failures,
                "total_successes": self._metrics.total_successes,
                "total_rejected": self._metrics.total_rejected,
                "consecutive_failures": self._metrics.consecutive_failures,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
        }
