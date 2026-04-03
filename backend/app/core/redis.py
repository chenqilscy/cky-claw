"""Redis 连接管理。"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局 Redis 连接池
_pool: aioredis.ConnectionPool | None = None
_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端实例（懒初始化连接池）。"""
    global _pool, _client
    if _client is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
        )
        _client = aioredis.Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    """关闭 Redis 连接池。"""
    global _pool, _client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
    logger.info("Redis connection pool closed")
