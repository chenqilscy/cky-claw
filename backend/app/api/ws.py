"""WebSocket 审批通道 — 实时推送审批事件。

客户端通过 WS /api/ws/approvals?token=xxx 连接，
后端通过 Redis pub/sub 接收审批事件，并广播给所有活跃 WebSocket 客户端。
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.auth import decode_access_token
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter()

# Redis channel 名称
APPROVAL_CHANNEL = "ckyclaw:approvals"

# 活跃 WebSocket 连接集合
_active_connections: set[WebSocket] = set()

# Redis 订阅后台任务
_subscriber_task: asyncio.Task[None] | None = None


async def publish_approval_event(event_type: str, data: dict) -> None:
    """发布审批事件到 Redis channel。

    Args:
        event_type: 事件类型 (approval_created / approval_resolved)
        data: 事件数据
    """
    try:
        r = await get_redis()
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        await r.publish(APPROVAL_CHANNEL, payload)
    except Exception:
        logger.exception("Failed to publish approval event to Redis")


async def _broadcast(message: str) -> None:
    """向所有活跃 WebSocket 连接广播消息。"""
    dead: list[WebSocket] = []
    for ws in _active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _active_connections.discard(ws)


async def _redis_subscriber() -> None:
    """Redis 订阅后台任务 — 监听审批 channel 并广播到 WebSocket。"""
    while True:
        try:
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe(APPROVAL_CHANNEL)
            logger.info("Redis subscriber started on channel: %s", APPROVAL_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    await _broadcast(message["data"])
        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
            with suppress(Exception):
                await pubsub.unsubscribe(APPROVAL_CHANNEL)  # type: ignore[possibly-undefined]
                await pubsub.aclose()  # type: ignore[possibly-undefined]
            return
        except Exception:
            logger.exception("Redis subscriber error, reconnecting in 3s")
            await asyncio.sleep(3)


async def start_subscriber() -> None:
    """启动 Redis 订阅后台任务。"""
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        _subscriber_task = asyncio.create_task(_redis_subscriber())
        logger.info("Approval WebSocket subscriber task started")


async def stop_subscriber() -> None:
    """停止 Redis 订阅后台任务。"""
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        _subscriber_task.cancel()
        with suppress(asyncio.CancelledError):
            await _subscriber_task
        _subscriber_task = None
        logger.info("Approval WebSocket subscriber task stopped")


@router.websocket("/api/ws/approvals")
async def approval_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Token"),
) -> None:
    """审批 WebSocket 端点。

    握手时验证 JWT Token，成功后持续推送审批事件。
    支持 ping/pong 心跳保活。
    """
    # JWT 认证
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    _active_connections.add(websocket)
    logger.info("WebSocket client connected (user=%s)", payload.get("sub"))

    try:
        while True:
            # 接收客户端消息（心跳 ping 或其他指令）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)
        logger.info("WebSocket client disconnected (user=%s)", payload.get("sub"))
