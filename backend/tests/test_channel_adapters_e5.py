"""E5 海外消息网关测试 — Telegram + Discord 适配器。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.channel_adapters.discord import DiscordAdapter
from app.services.channel_adapters.telegram import TelegramAdapter

# ---------------------------------------------------------------------------
# Telegram 适配器
# ---------------------------------------------------------------------------


class TestTelegramVerify:
    """Telegram 请求验证测试。"""

    def test_verify_no_secret(self) -> None:
        """未配置 secret_token 时跳过验证。"""
        adapter = TelegramAdapter()
        assert adapter.verify_request({}, b"", {}) is True

    def test_verify_matching_token(self) -> None:
        """匹配的 secret_token。"""
        adapter = TelegramAdapter()
        headers = {"X-Telegram-Bot-Api-Secret-Token": "my-secret"}
        assert adapter.verify_request(headers, b"", {"secret_token": "my-secret"}) is True

    def test_verify_mismatching_token(self) -> None:
        """不匹配的 secret_token。"""
        adapter = TelegramAdapter()
        headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong"}
        assert adapter.verify_request(headers, b"", {"secret_token": "my-secret"}) is False

    def test_verify_missing_header(self) -> None:
        """缺少 header 时验证失败。"""
        adapter = TelegramAdapter()
        assert adapter.verify_request({}, b"", {"secret_token": "my-secret"}) is False

    def test_verify_lowercase_header(self) -> None:
        """小写 header 也能匹配。"""
        adapter = TelegramAdapter()
        headers = {"x-telegram-bot-api-secret-token": "my-secret"}
        assert adapter.verify_request(headers, b"", {"secret_token": "my-secret"}) is True


class TestTelegramParse:
    """Telegram 消息解析测试。"""

    def _make_update(self, text: str = "hello", chat_id: int = 123, user_id: int = 456) -> bytes:
        """构造 Telegram Update JSON。"""
        return json.dumps({
            "update_id": 1,
            "message": {
                "message_id": 10,
                "from": {"id": user_id, "first_name": "Test"},
                "chat": {"id": chat_id, "type": "private"},
                "text": text,
            },
        }).encode()

    def test_parse_text_message(self) -> None:
        """解析文本消息。"""
        adapter = TelegramAdapter()
        msg = adapter.parse_message(self._make_update("hello world"), {})
        assert msg is not None
        assert msg.content == "hello world"
        assert msg.sender_id == "456"
        assert msg.raw_data["chat_id"] == "123"

    def test_parse_channel_post(self) -> None:
        """解析频道消息。"""
        adapter = TelegramAdapter()
        data = json.dumps({
            "update_id": 2,
            "channel_post": {
                "message_id": 20,
                "chat": {"id": -100, "type": "channel"},
                "text": "channel msg",
            },
        }).encode()
        msg = adapter.parse_message(data, {})
        assert msg is not None
        assert msg.content == "channel msg"

    def test_parse_no_text(self) -> None:
        """无文本消息（如图片）返回 None。"""
        adapter = TelegramAdapter()
        data = json.dumps({
            "update_id": 3,
            "message": {
                "message_id": 30,
                "from": {"id": 1},
                "chat": {"id": 2},
                "photo": [{"file_id": "abc"}],
            },
        }).encode()
        msg = adapter.parse_message(data, {})
        assert msg is None

    def test_parse_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = TelegramAdapter()
        assert adapter.parse_message(b"not json", {}) is None

    def test_parse_empty_update(self) -> None:
        """空 update 返回 None。"""
        adapter = TelegramAdapter()
        assert adapter.parse_message(b"{}", {}) is None


class TestTelegramVerification:
    """Telegram URL 验证测试。"""

    def test_no_verification(self) -> None:
        """Telegram 无需 URL 验证。"""
        adapter = TelegramAdapter()
        assert adapter.handle_verification(b"{}", {}, {}) is None


class TestTelegramSend:
    """Telegram 消息推送测试。"""

    @pytest.mark.asyncio
    async def test_send_no_token(self) -> None:
        """无 bot_token 推送失败。"""
        adapter = TelegramAdapter()
        assert await adapter.send_message({}, "123", "hello") is False

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """推送成功。"""
        adapter = TelegramAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}

        with patch("app.services.channel_adapters.telegram.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp),
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await adapter.send_message({"bot_token": "123:ABC"}, "456", "hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_api_error(self) -> None:
        """API 返回错误。"""
        adapter = TelegramAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": False, "description": "bad request"}

        with patch("app.services.channel_adapters.telegram.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp),
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await adapter.send_message({"bot_token": "123:ABC"}, "456", "hello")
        assert result is False


# ---------------------------------------------------------------------------
# Discord 适配器
# ---------------------------------------------------------------------------


class TestDiscordVerify:
    """Discord 请求验证测试。"""

    def test_verify_no_public_key(self) -> None:
        """未配置 public_key 时跳过验证。"""
        adapter = DiscordAdapter()
        assert adapter.verify_request({}, b"", {}) is True

    def test_verify_missing_headers(self) -> None:
        """缺少签名 header 时失败。"""
        adapter = DiscordAdapter()
        assert adapter.verify_request({}, b"", {"public_key": "abc"}) is False


class TestDiscordParse:
    """Discord 消息解析测试。"""

    def test_parse_ping(self) -> None:
        """PING 不是消息。"""
        adapter = DiscordAdapter()
        data = json.dumps({"type": 1}).encode()
        assert adapter.parse_message(data, {}) is None

    def test_parse_application_command(self) -> None:
        """解析 APPLICATION_COMMAND。"""
        adapter = DiscordAdapter()
        data = json.dumps({
            "type": 2,
            "id": "cmd1",
            "data": {"name": "ask", "options": [{"name": "q", "value": "hello"}]},
            "member": {"user": {"id": "789"}},
            "channel_id": "ch1",
            "guild_id": "g1",
            "token": "tok1",
        }).encode()
        msg = adapter.parse_message(data, {})
        assert msg is not None
        assert msg.content == "ask q=hello"
        assert msg.sender_id == "789"
        assert msg.raw_data["channel_id"] == "ch1"

    def test_parse_message_component(self) -> None:
        """解析 MESSAGE_COMPONENT。"""
        adapter = DiscordAdapter()
        data = json.dumps({
            "type": 3,
            "id": "int1",
            "data": {"custom_id": "btn_confirm", "component_type": 2},
            "member": {"user": {"id": "111"}},
            "channel_id": "ch2",
            "token": "tok2",
        }).encode()
        msg = adapter.parse_message(data, {})
        assert msg is not None
        assert msg.content == "btn_confirm"
        assert msg.message_type == "event"

    def test_parse_unknown_type(self) -> None:
        """未知 type 返回 None。"""
        adapter = DiscordAdapter()
        data = json.dumps({"type": 99}).encode()
        assert adapter.parse_message(data, {}) is None

    def test_parse_invalid_json(self) -> None:
        """无效 JSON。"""
        adapter = DiscordAdapter()
        assert adapter.parse_message(b"bad", {}) is None

    def test_parse_command_no_options(self) -> None:
        """无选项的命令。"""
        adapter = DiscordAdapter()
        data = json.dumps({
            "type": 2,
            "data": {"name": "help"},
            "user": {"id": "222"},
        }).encode()
        msg = adapter.parse_message(data, {})
        assert msg is not None
        assert msg.content == "help"


class TestDiscordVerification:
    """Discord PING 验证测试。"""

    def test_ping_pong(self) -> None:
        """PING → PONG。"""
        adapter = DiscordAdapter()
        data = json.dumps({"type": 1}).encode()
        result = adapter.handle_verification(data, {}, {})
        assert result is not None
        assert json.loads(result)["type"] == 1

    def test_non_ping(self) -> None:
        """非 PING 返回 None。"""
        adapter = DiscordAdapter()
        data = json.dumps({"type": 2}).encode()
        assert adapter.handle_verification(data, {}, {}) is None


class TestDiscordSend:
    """Discord 消息推送测试。"""

    @pytest.mark.asyncio
    async def test_send_no_config(self) -> None:
        """无配置推送失败。"""
        adapter = DiscordAdapter()
        assert await adapter.send_message({}, "ch1", "hello") is False

    @pytest.mark.asyncio
    async def test_send_via_webhook(self) -> None:
        """通过 Webhook URL 推送。"""
        adapter = DiscordAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("app.services.channel_adapters.discord.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp),
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await adapter.send_message(
                {"webhook_url": "https://discord.com/api/webhooks/123/abc"},
                "", "hello",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_via_bot(self) -> None:
        """通过 Bot API 推送。"""
        adapter = DiscordAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("app.services.channel_adapters.discord.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp),
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await adapter.send_message(
                {"bot_token": "Bot-Token-123"}, "ch1", "hello",
            )
        assert result is True


# ---------------------------------------------------------------------------
# 注册表集成
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    """适配器注册表测试。"""

    def test_telegram_registered(self) -> None:
        """Telegram 适配器已注册。"""
        from app.services.channel_adapters import get_adapter
        adapter = get_adapter("telegram")
        assert adapter is not None
        assert isinstance(adapter, TelegramAdapter)

    def test_discord_registered(self) -> None:
        """Discord 适配器已注册。"""
        from app.services.channel_adapters import get_adapter
        adapter = get_adapter("discord")
        assert adapter is not None
        assert isinstance(adapter, DiscordAdapter)
