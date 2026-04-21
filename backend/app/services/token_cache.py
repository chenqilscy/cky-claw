"""Token 缓存服务 — 基于 Redis 的 IM/OAuth access_token 缓存。

避免对微信/企微/飞书等平台 API 频繁获取 access_token，
通过 Redis 缓存 token 并设置略小于实际有效期的 TTL。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.redis import get_redis

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# 缓存 key 前缀
_PREFIX = "kasaya:token:"

# 默认 TTL：7000 秒（平台一般有效期 7200 秒，预留 200 秒安全余量）
_DEFAULT_TTL = 7000


async def get_or_fetch(
    cache_key: str,
    fetch_fn: Callable[[], Awaitable[str | None]],
    ttl: int = _DEFAULT_TTL,
) -> str | None:
    """从 Redis 缓存获取 token，缓存未命中则调用 fetch_fn 获取并写入缓存。

    Args:
        cache_key: 缓存标识（自动添加前缀），如 "wecom:{corpid}"。
        fetch_fn: 异步获取 token 的回调函数。
        ttl: 缓存过期时间（秒），默认 7000。

    Returns:
        token 字符串，或获取失败返回 None。
    """
    full_key = f"{_PREFIX}{cache_key}"

    try:
        redis = await get_redis()
        cached: str | None = await redis.get(full_key)
        if cached:
            logger.debug("Token 缓存命中: %s", full_key)
            return cached
    except Exception:
        # Redis 不可用时降级为直接获取
        logger.warning("Redis 不可用，降级为直接获取 token: %s", full_key)

    # 缓存未命中或 Redis 异常，调用实际获取逻辑
    token = await fetch_fn()
    if not token:
        return None

    try:
        redis = await get_redis()
        await redis.setex(full_key, ttl, token)
        logger.debug("Token 已缓存: %s (TTL=%ds)", full_key, ttl)
    except Exception:
        # 写缓存失败不影响功能
        logger.warning("Token 缓存写入失败: %s", full_key)

    return token
