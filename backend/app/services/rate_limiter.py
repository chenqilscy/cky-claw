"""Rate Limiter — 基于 Redis 滑动窗口的限流服务。"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.core.redis import get_redis

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """限流超出异常。"""

    def __init__(self, limit_type: str, limit: int, window: int = 60) -> None:
        super().__init__(
            status_code=429,
            detail=f"Rate limit exceeded: {limit_type} limit is {limit} per {window}s",
        )


async def check_rate_limit(
    provider_id: uuid.UUID,
    *,
    rpm_limit: int | None = None,
    tpm_limit: int | None = None,
    token_count: int = 0,
) -> None:
    """检查 Provider 限流。使用 Redis 滑动窗口计数器。

    Args:
        provider_id: Provider UUID
        rpm_limit: 每分钟请求数上限（None=不限制）
        tpm_limit: 每分钟 Token 数上限（None=不限制）
        token_count: 本次请求的预估 Token 数

    Raises:
        RateLimitExceeded: 超出限制时抛出 HTTP 429
    """
    if rpm_limit is None and tpm_limit is None:
        return

    redis = await get_redis()
    now = time.time()
    window = 60  # 1 分钟窗口

    pid = str(provider_id)

    # RPM 检查——滑动窗口计数
    if rpm_limit is not None:
        rpm_key = f"rl:rpm:{pid}"
        pipe = redis.pipeline()
        pipe.zremrangebyscore(rpm_key, 0, now - window)
        pipe.zcard(rpm_key)
        pipe.zadd(rpm_key, {f"{now}:{id(now)}": now})
        pipe.expire(rpm_key, window + 1)
        results = await pipe.execute()
        current_rpm = results[1]  # zcard 结果
        if current_rpm >= rpm_limit:
            # 回滚刚刚添加的成员
            await redis.zremrangebyscore(rpm_key, now, now + 0.001)
            logger.warning("RPM limit exceeded for provider %s: %d >= %d", pid, current_rpm, rpm_limit)
            raise RateLimitExceeded("RPM", rpm_limit)

    # TPM 检查——滑动窗口累计 Token
    if tpm_limit is not None and token_count > 0:
        tpm_key = f"rl:tpm:{pid}"
        pipe = redis.pipeline()
        pipe.zremrangebyscore(tpm_key, 0, now - window)
        pipe.zrangebyscore(tpm_key, now - window, "+inf", withscores=False)
        results = await pipe.execute()
        # 累加窗口内所有 token 数
        current_tpm = 0
        for m in results[1]:
            try:
                token_str = m if isinstance(m, str) else m.decode("utf-8")
                current_tpm += int(token_str.split(":")[0])
            except (ValueError, AttributeError):
                continue
        if current_tpm + token_count > tpm_limit:
            logger.warning(
                "TPM limit exceeded for provider %s: %d + %d > %d",
                pid, current_tpm, token_count, tpm_limit,
            )
            raise RateLimitExceeded("TPM", tpm_limit)
        # 记录本次 token 数
        await redis.zadd(tpm_key, {f"{token_count}:{now}": now})
        await redis.expire(tpm_key, window + 1)


async def get_rate_limit_status(
    provider_id: uuid.UUID,
) -> dict[str, int]:
    """查询当前限流窗口内的使用量。"""
    redis = await get_redis()
    now = time.time()
    window = 60
    pid = str(provider_id)

    rpm_key = f"rl:rpm:{pid}"
    tpm_key = f"rl:tpm:{pid}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(rpm_key, 0, now - window)
    pipe.zcard(rpm_key)
    pipe.zremrangebyscore(tpm_key, 0, now - window)
    pipe.zrangebyscore(tpm_key, now - window, "+inf", withscores=False)
    results = await pipe.execute()

    current_rpm = results[1]
    current_tpm = 0
    for m in results[3]:
        try:
            token_str = m if isinstance(m, str) else m.decode("utf-8")
            current_tpm += int(token_str.split(":")[0])
        except (ValueError, AttributeError):
            continue

    return {"current_rpm": current_rpm, "current_tpm": current_tpm}
