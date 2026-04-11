"""ToolMiddleware — 工具执行中间件管道。

提供 before_execute / after_execute 异步钩子抽象，支持可插拔管道。
中间件按注册顺序执行 before_execute，逆序执行 after_execute（洋葱模型）。

内置中间件：
- CacheMiddleware: 工具结果缓存（相同参数直接返回缓存）
- LoopGuardMiddleware: 循环调用检测（同一工具+参数重复 N 次则拦截）
- TimeoutMiddleware: 全局超时控制
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionContext:
    """工具执行上下文，在中间件管道中传递。"""

    tool_name: str
    """工具名称"""

    arguments: dict[str, Any]
    """调用参数"""

    agent_name: str
    """所属 Agent 名称"""

    run_id: str | None = None
    """运行 ID"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """中间件可读写的共享元数据"""


@dataclass
class MiddlewareResult:
    """中间件处理结果。"""

    should_continue: bool = True
    """是否继续执行管道。False 时短路返回 result。"""

    result: str | None = None
    """短路返回时的结果字符串。"""

    modified_arguments: dict[str, Any] | None = None
    """修改后的参数（替换原始参数）。"""


class ToolMiddleware(ABC):
    """工具中间件抽象基类。"""

    @property
    def name(self) -> str:
        """中间件名称。"""
        return type(self).__name__

    @abstractmethod
    async def before_execute(
        self,
        context: ToolExecutionContext,
    ) -> MiddlewareResult:
        """工具执行前调用。

        Args:
            context: 工具执行上下文

        Returns:
            MiddlewareResult，should_continue=False 时短路
        """
        ...

    async def after_execute(
        self,
        context: ToolExecutionContext,
        result: str,
        duration: float,
    ) -> str:
        """工具执行后调用（默认直通）。

        Args:
            context: 工具执行上下文
            result: 工具执行结果
            duration: 执行耗时（秒）

        Returns:
            可能被修改的结果字符串
        """
        return result


class ToolMiddlewarePipeline:
    """工具中间件管道。

    按注册顺序执行 before_execute（洋葱模型前半），
    逆序执行 after_execute（洋葱模型后半）。

    用法::

        pipeline = ToolMiddlewarePipeline([
            CacheMiddleware(ttl=60),
            LoopGuardMiddleware(max_repeats=3),
            TimeoutMiddleware(timeout=30),
        ])
        result = await pipeline.execute(context, tool_fn)
    """

    def __init__(self, middlewares: list[ToolMiddleware] | None = None) -> None:
        self._middlewares: list[ToolMiddleware] = list(middlewares or [])

    @property
    def middlewares(self) -> list[ToolMiddleware]:
        """中间件列表（只读）。"""
        return list(self._middlewares)

    def add(self, middleware: ToolMiddleware) -> None:
        """追加中间件。"""
        self._middlewares.append(middleware)

    async def execute(
        self,
        context: ToolExecutionContext,
        tool_fn: Any,
        arguments: dict[str, Any],
    ) -> str:
        """执行中间件管道 + 工具函数。

        Args:
            context: 工具执行上下文
            tool_fn: 工具的 execute 方法（async callable，接受 arguments dict，返回 str）
            arguments: 原始参数

        Returns:
            工具执行结果字符串
        """
        current_args = dict(arguments)
        executed_middlewares: list[ToolMiddleware] = []

        # ── before_execute 阶段（正序）──
        for mw in self._middlewares:
            try:
                mr = await mw.before_execute(context)
            except Exception as e:
                logger.exception("Middleware '%s' before_execute error: %s", mw.name, e)
                mr = MiddlewareResult()  # 出错时继续

            executed_middlewares.append(mw)

            if mr.modified_arguments is not None:
                current_args = mr.modified_arguments

            if not mr.should_continue:
                logger.debug("Middleware '%s' short-circuited tool '%s'", mw.name, context.tool_name)
                return mr.result or ""

        # ── 执行工具 ──
        start = time.monotonic()
        result = await tool_fn(current_args)
        duration = time.monotonic() - start

        # ── after_execute 阶段（逆序）──
        for mw in reversed(executed_middlewares):
            try:
                result = await mw.after_execute(context, result, duration)
            except Exception as e:
                logger.exception("Middleware '%s' after_execute error: %s", mw.name, e)

        return result


# ───────────────────────────────── 内置中间件 ─────────────────────────────────


def _args_hash(tool_name: str, arguments: dict[str, Any]) -> str:
    """计算工具调用的确定性哈希。"""
    key = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class CacheMiddleware(ToolMiddleware):
    """工具结果缓存中间件。

    相同工具名 + 参数在 TTL 内直接返回缓存，跳过实际执行。
    """

    def __init__(self, ttl: float = 60.0, max_entries: int = 100) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._cache: dict[str, tuple[str, float]] = {}

    @property
    def name(self) -> str:
        return "CacheMiddleware"

    async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
        """检查缓存命中。"""
        key = _args_hash(context.tool_name, context.arguments)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                context.metadata["cache_hit"] = True
                logger.debug("CacheMiddleware: HIT for '%s'", context.tool_name)
                return MiddlewareResult(should_continue=False, result=result)
            else:
                del self._cache[key]
        context.metadata["cache_hit"] = False
        context.metadata["_cache_key"] = key
        return MiddlewareResult()

    async def after_execute(self, context: ToolExecutionContext, result: str, duration: float) -> str:
        """将结果写入缓存。"""
        key = context.metadata.get("_cache_key")
        if key and not result.startswith("Error:"):
            # LRU 淘汰
            if len(self._cache) >= self._max_entries:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (result, time.monotonic())
        return result

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """当前缓存条目数。"""
        return len(self._cache)


class LoopGuardMiddleware(ToolMiddleware):
    """循环调用检测中间件。

    检测同一工具 + 相同参数在同一 run 中被重复调用 N 次，超限则拦截。
    防止 Agent 陷入"工具调用死循环"。
    """

    def __init__(self, max_repeats: int = 3) -> None:
        self._max_repeats = max_repeats
        self._call_counts: dict[str, int] = defaultdict(int)
        self._max_keys = 500  # 防止无限哈希 key 导致内存泄漏

    @property
    def name(self) -> str:
        return "LoopGuardMiddleware"

    async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
        """检查重复调用次数。"""
        key = _args_hash(context.tool_name, context.arguments)
        self._call_counts[key] += 1
        count = self._call_counts[key]

        # 防止无限哈希 key 导致内存泄漏
        if len(self._call_counts) > self._max_keys:
            # 保留计数 > 1 的 key（有重复调用风险），清理仅调用一次的
            single_keys = [k for k, v in self._call_counts.items() if v <= 1 and k != key]
            for k in single_keys[:len(self._call_counts) - self._max_keys]:
                del self._call_counts[k]

        if count > self._max_repeats:
            msg = (
                f"Error: LoopGuard blocked '{context.tool_name}' — "
                f"repeated {count} times with same arguments (max {self._max_repeats}). "
                f"Try a different approach."
            )
            logger.warning("LoopGuardMiddleware: %s", msg)
            return MiddlewareResult(should_continue=False, result=msg)

        return MiddlewareResult()

    def reset(self) -> None:
        """重置计数器（新的 run 开始时调用）。"""
        self._call_counts.clear()


class TimeoutMiddleware(ToolMiddleware):
    """全局超时中间件。

    为所有工具调用设置统一超时，独立于 FunctionTool.timeout 和 RunConfig.tool_timeout。
    适用于管道级别的超时控制。
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "TimeoutMiddleware"

    async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
        """记录开始时间。"""
        context.metadata["_timeout_start"] = time.monotonic()
        context.metadata["_timeout_limit"] = self._timeout
        return MiddlewareResult()

    async def after_execute(self, context: ToolExecutionContext, result: str, duration: float) -> str:
        """检查执行时间（注意：实际超时由 pipeline 的 asyncio.wait_for 控制）。"""
        if duration > self._timeout:
            logger.warning(
                "TimeoutMiddleware: '%s' took %.1fs (limit %.1fs)",
                context.tool_name, duration, self._timeout,
            )
        return result


class RateLimitMiddleware(ToolMiddleware):
    """工具调用频率限制中间件。

    使用滑动窗口限制单个工具在时间窗口内的调用次数。
    """

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._call_times: dict[str, list[float]] = defaultdict(list)
        self._max_keys = 200  # 防止无限工具名导致内存泄漏

    @property
    def name(self) -> str:
        return "RateLimitMiddleware"

    async def before_execute(self, context: ToolExecutionContext) -> MiddlewareResult:
        """检查频率限制。"""
        now = time.monotonic()
        key = context.tool_name
        times = self._call_times[key]

        # 清理窗口外的记录
        cutoff = now - self._window
        self._call_times[key] = [t for t in times if t > cutoff]
        times = self._call_times[key]

        # 防止无限工具名导致内存泄漏：清理空列表的 key
        if len(self._call_times) > self._max_keys:
            empty_keys = [k for k, v in self._call_times.items() if not v]
            for k in empty_keys:
                del self._call_times[k]

        if len(times) >= self._max_calls:
            msg = (
                f"Error: RateLimit blocked '{context.tool_name}' — "
                f"{len(times)} calls in {self._window}s (max {self._max_calls}). "
                f"Please wait before retrying."
            )
            return MiddlewareResult(should_continue=False, result=msg)

        times.append(now)
        return MiddlewareResult()
