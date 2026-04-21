"""健康检查路由 — 含 DB/Redis 深度探测 + 系统信息。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["system"])

_PROBE_TIMEOUT = 2.0  # 秒


async def _probe_db() -> dict[str, Any]:
    """探测 PostgreSQL 连接。"""
    from sqlalchemy import text

    from app.core.database import async_session_factory

    start = time.monotonic()
    try:
        async with async_session_factory() as db:
            result = await db.execute(text("SELECT version()"))
            version = result.scalar()
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "ok", "latency_ms": latency_ms, "version": str(version)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


async def _probe_redis() -> dict[str, Any]:
    """探测 Redis 连接。"""
    start = time.monotonic()
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        pong: bool = await redis.ping()  # type: ignore[misc]
        info = await redis.info("server")
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return {
            "status": "ok" if pong else "error",
            "latency_ms": latency_ms,
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


@router.get("/health")
async def health_check() -> dict[str, str]:
    """轻量健康检查端点 — 适用于负载均衡器。"""
    return {"status": "ok", "service": "kasaya-backend"}


@router.get("/health/deep")
async def deep_health_check() -> dict[str, Any]:
    """深度健康检查 — 探测 DB + Redis 连接状态与延迟。"""
    try:
        db_result, redis_result = await asyncio.wait_for(
            _gather_probes(), timeout=_PROBE_TIMEOUT
        )
    except TimeoutError:
        db_result = {"status": "timeout"}
        redis_result = {"status": "timeout"}

    overall = "ok" if (
        db_result.get("status") == "ok" and redis_result.get("status") == "ok"
    ) else "degraded"

    return {
        "status": overall,
        "service": "kasaya-backend",
        "components": {
            "database": db_result,
            "redis": redis_result,
        },
    }


async def _gather_probes() -> tuple[dict[str, Any], dict[str, Any]]:
    """并行执行 DB 和 Redis 探测。"""
    db_task = asyncio.create_task(_probe_db())
    redis_task = asyncio.create_task(_probe_redis())
    return await db_task, await redis_task


@router.get("/system/info")
async def system_info() -> dict[str, Any]:
    """返回系统可观测性配置信息，供前端 APM 面板展示。"""
    return {
        "otel_enabled": settings.otel_enabled,
        "otel_service_name": settings.otel_service_name,
        "otel_exporter_endpoint": settings.otel_exporter_endpoint,
        "jaeger_ui_url": settings.jaeger_ui_url,
        "prometheus_ui_url": settings.prometheus_ui_url,
    }
