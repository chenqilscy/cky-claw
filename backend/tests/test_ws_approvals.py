"""WebSocket 审批通道测试。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.ws import (
    APPROVAL_CHANNEL,
    _active_connections,
    _broadcast,
    publish_approval_event,
)
from app.core.redis import close_redis


class TestPublishApprovalEvent:
    """publish_approval_event 测试。"""

    @pytest.mark.asyncio
    async def test_publish_event_to_redis(self) -> None:
        """正常发布事件到 Redis channel。"""
        mock_redis = AsyncMock()
        with patch("app.api.ws.get_redis", return_value=mock_redis):
            await publish_approval_event("approval_created", {"id": "test-123"})
        mock_redis.publish.assert_called_once()
        args = mock_redis.publish.call_args
        assert args[0][0] == APPROVAL_CHANNEL
        payload = json.loads(args[0][1])
        assert payload["type"] == "approval_created"
        assert payload["data"]["id"] == "test-123"

    @pytest.mark.asyncio
    async def test_publish_handles_redis_error(self) -> None:
        """Redis 不可用时不抛异常。"""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        with patch("app.api.ws.get_redis", return_value=mock_redis):
            # 不应抛异常
            await publish_approval_event("approval_created", {"id": "test-456"})

    @pytest.mark.asyncio
    async def test_publish_serializes_uuid_and_datetime(self) -> None:
        """UUID 和 datetime 可被序列化。"""
        mock_redis = AsyncMock()
        with patch("app.api.ws.get_redis", return_value=mock_redis):
            await publish_approval_event("approval_resolved", {
                "id": str(uuid.uuid4()),
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            })
        mock_redis.publish.assert_called_once()


class TestBroadcast:
    """_broadcast 测试。"""

    @pytest.mark.asyncio
    async def test_broadcast_to_active_connections(self) -> None:
        """广播消息到所有活跃连接。"""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        _active_connections.clear()
        _active_connections.add(ws1)
        _active_connections.add(ws2)
        try:
            await _broadcast('{"type":"test"}')
            ws1.send_text.assert_called_once_with('{"type":"test"}')
            ws2.send_text.assert_called_once_with('{"type":"test"}')
        finally:
            _active_connections.clear()

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self) -> None:
        """发送失败的连接被自动移除。"""
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = ConnectionError("closed")
        _active_connections.clear()
        _active_connections.add(ws_alive)
        _active_connections.add(ws_dead)
        try:
            await _broadcast("test")
            assert ws_alive in _active_connections
            assert ws_dead not in _active_connections
        finally:
            _active_connections.clear()

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self) -> None:
        """无连接时广播不报错。"""
        _active_connections.clear()
        await _broadcast("test")  # 不应抛异常


class TestRedisModule:
    """Redis 连接管理测试。"""

    @pytest.mark.asyncio
    async def test_close_redis_idempotent(self) -> None:
        """多次关闭不报错。"""
        await close_redis()
        await close_redis()


class TestWebSocketEndpoint:
    """WebSocket 端点认证测试。"""

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self) -> None:
        """无效 token 应被拒绝。"""
        from app.api.ws import approval_websocket

        ws = AsyncMock()
        with patch("app.api.ws.decode_access_token", return_value=None):
            await approval_websocket(ws, token="bad-token")
        ws.close.assert_called_once_with(code=4001, reason="Invalid token")
        # 不应调用 accept
        ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_token_accepted(self) -> None:
        """有效 token 应接受连接。"""
        from fastapi import WebSocketDisconnect

        from app.api.ws import approval_websocket

        ws = AsyncMock()
        ws.receive_text.side_effect = WebSocketDisconnect()
        with patch("app.api.ws.decode_access_token", return_value={"sub": "user-1"}):
            await approval_websocket(ws, token="good-token")
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_pong(self) -> None:
        """心跳 ping 应返回 pong。"""
        from fastapi import WebSocketDisconnect

        from app.api.ws import approval_websocket

        ws = AsyncMock()
        # 先返回 ping，再断开
        ws.receive_text.side_effect = ["ping", WebSocketDisconnect()]
        with patch("app.api.ws.decode_access_token", return_value={"sub": "user-1"}):
            await approval_websocket(ws, token="good-token")
        ws.send_text.assert_called_with("pong")
