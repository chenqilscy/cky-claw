"""Discord Bot IM 渠道适配器。

实现 Discord Webhook / Interactions 消息接入：
- 请求签名验证（Ed25519 签名校验）
- 消息解析（JSON Interaction → ChannelMessage）
- URL 验证回调（PING → PONG 响应）
- 消息推送（Webhook URL 或 Bot API）

app_config 必需字段：
- webhook_url: Discord Webhook URL（用于消息推送）

app_config 可选字段：
- public_key: Discord Application Public Key（Ed25519 签名验证）
- bot_token: Discord Bot Token（用于 API 调用）
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# Discord Interaction 类型
_INTERACTION_PING = 1
_INTERACTION_APPLICATION_COMMAND = 2
_INTERACTION_MESSAGE_COMPONENT = 3

# Discord API 基地址
_DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordAdapter(ChannelAdapter):
    """Discord 渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证 Discord Interaction 请求（Ed25519 签名）。

        Discord 使用 Ed25519 签名验证：
        - X-Signature-Ed25519: 签名
        - X-Signature-Timestamp: 时间戳
        - 验证消息 = timestamp + body

        如未配置 public_key 则跳过验证。
        """
        public_key = app_config.get("public_key", "")
        if not public_key:
            return True

        signature = (
            headers.get("X-Signature-Ed25519", "")
            or headers.get("x-signature-ed25519", "")
        )
        timestamp = (
            headers.get("X-Signature-Timestamp", "")
            or headers.get("x-signature-timestamp", "")
        )

        if not signature or not timestamp:
            return False

        try:
            # 尝试使用 PyNaCl 验证签名
            from nacl.signing import VerifyKey
            verify_key = VerifyKey(bytes.fromhex(public_key))
            message = timestamp.encode() + body
            verify_key.verify(message, bytes.fromhex(signature))
            return True
        except ImportError:
            logger.warning("Discord 签名验证需要 PyNaCl 库，跳过验证")
            return True
        except Exception:
            logger.warning("Discord 签名验证失败")
            return False

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """从 Discord Interaction JSON 解析消息。

        支持 APPLICATION_COMMAND 和 MESSAGE_COMPONENT 类型。
        PING 类型由 handle_verification 处理。
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Discord 消息解析失败: 无效 JSON")
            return None

        interaction_type = data.get("type")

        # PING 不是消息
        if interaction_type == _INTERACTION_PING:
            return None

        # APPLICATION_COMMAND
        if interaction_type == _INTERACTION_APPLICATION_COMMAND:
            cmd_data = data.get("data", {})
            content = cmd_data.get("name", "")
            # 拼接选项
            options = cmd_data.get("options", [])
            if options:
                option_parts = [f"{o.get('name')}={o.get('value')}" for o in options]
                content = f"{content} {' '.join(option_parts)}"

            member = data.get("member", {})
            user = member.get("user", data.get("user", {}))
            sender_id = str(user.get("id", ""))

            return ChannelMessage(
                sender_id=sender_id,
                content=content,
                message_type="text",
                raw_data={
                    "interaction_id": data.get("id"),
                    "channel_id": data.get("channel_id"),
                    "guild_id": data.get("guild_id"),
                    "token": data.get("token"),
                },
            )

        # MESSAGE_COMPONENT
        if interaction_type == _INTERACTION_MESSAGE_COMPONENT:
            comp_data = data.get("data", {})
            member = data.get("member", {})
            user = member.get("user", data.get("user", {}))
            sender_id = str(user.get("id", ""))

            return ChannelMessage(
                sender_id=sender_id,
                content=comp_data.get("custom_id", ""),
                message_type="event",
                raw_data={
                    "interaction_id": data.get("id"),
                    "channel_id": data.get("channel_id"),
                    "component_type": comp_data.get("component_type"),
                    "token": data.get("token"),
                },
            )

        return None

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理 Discord PING 验证（回复 PONG）。"""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if data.get("type") == _INTERACTION_PING:
            return json.dumps({"type": 1})  # PONG

        return None

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过 Discord Webhook 推送消息。

        优先使用 webhook_url（简单模式）。
        如配置了 bot_token + channel_id 则使用 Bot API。

        Args:
            app_config: 需包含 webhook_url 或 bot_token。
            recipient_id: channel_id 或 user_id。
            content: 消息文本。
        """
        # 方式 1: Webhook URL
        webhook_url = app_config.get("webhook_url", "")
        if webhook_url:
            return await self._send_via_webhook(webhook_url, content)

        # 方式 2: Bot API
        bot_token = app_config.get("bot_token", "")
        if bot_token:
            return await self._send_via_bot(bot_token, recipient_id, content)

        logger.error("Discord 推送失败: 未配置 webhook_url 或 bot_token")
        return False

    async def _send_via_webhook(self, webhook_url: str, content: str) -> bool:
        """通过 Webhook URL 发送。"""
        payload = {"content": content}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    return True
                logger.warning("Discord Webhook HTTP %d", resp.status_code)
                return False
        except httpx.HTTPError as exc:
            logger.error("Discord Webhook 推送异常: %s", exc)
            return False

    async def _send_via_bot(
        self, bot_token: str, channel_id: str, content: str
    ) -> bool:
        """通过 Bot API 发送。"""
        url = f"{_DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {bot_token}"}
        payload = {"content": content}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return True
                logger.warning("Discord Bot API HTTP %d", resp.status_code)
                return False
        except httpx.HTTPError as exc:
            logger.error("Discord Bot API 推送异常: %s", exc)
            return False
