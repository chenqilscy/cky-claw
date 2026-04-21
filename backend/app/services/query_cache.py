"""通用查询缓存 — 基于 Redis 的 cache-aside 模式。

与 token_cache 不同，query_cache 缓存的是 JSON 可序列化的数据结构，
适用于高频读、低频写的查询结果缓存。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, TypeVar

from app.core.redis import get_redis

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 缓存 key 前缀
_PREFIX = "kasaya:qcache:"

# 默认 TTL：5 分钟
_DEFAULT_TTL = 300


async def get_or_fetch(
    cache_key: str,
    fetch_fn: Callable[[], Awaitable[Any]],
    ttl: int = _DEFAULT_TTL,
) -> Any:
    """从 Redis 缓存获取查询结果，缓存未命中则调用 fetch_fn 获取并写入缓存。

    Args:
        cache_key: 缓存标识（自动添加前缀）。
        fetch_fn: 异步获取数据的回调函数，返回 JSON 可序列化对象。
        ttl: 缓存过期时间（秒），默认 300。

    Returns:
        缓存的或新获取的数据。
    """
    full_key = f"{_PREFIX}{cache_key}"

    try:
        redis = await get_redis()
        cached: str | None = await redis.get(full_key)
        if cached is not None:
            logger.debug("Query cache hit: %s", full_key)
            return json.loads(cached)
    except Exception:
        logger.warning("Redis 不可用，降级为直接查询: %s", full_key)

    # 缓存未命中，调用实际查询逻辑
    result = await fetch_fn()

    try:
        redis = await get_redis()
        await redis.setex(full_key, ttl, json.dumps(result, default=str))
        logger.debug("Query cached: %s (TTL=%ds)", full_key, ttl)
    except Exception:
        logger.warning("Query cache 写入失败: %s", full_key)

    return result


async def invalidate(cache_key: str) -> None:
    """删除指定缓存。"""
    full_key = f"{_PREFIX}{cache_key}"
    try:
        redis = await get_redis()
        await redis.delete(full_key)
        logger.debug("Query cache invalidated: %s", full_key)
    except Exception:
        logger.warning("Query cache 删除失败: %s", full_key)


async def invalidate_pattern(pattern: str) -> None:
    """按模式删除缓存（SCAN + DELETE，避免 KEYS 阻塞）。"""
    full_pattern = f"{_PREFIX}{pattern}"
    try:
        redis = await get_redis()
        cursor: int = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=full_pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
        logger.debug("Query cache pattern invalidated: %s", full_pattern)
    except Exception:
        logger.warning("Query cache 模式删除失败: %s", full_pattern)
