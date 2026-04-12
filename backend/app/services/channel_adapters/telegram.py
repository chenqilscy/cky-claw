"""Telegram Bot IM 渠道适配器。

实现 Telegram Bot API Webhook 消息接入：
- 请求签名验证（基于 secret_token 头部校验）
- 消息解析（JSON Update → ChannelMessage）
- URL 验证回调（Telegram 无需专门的验证机制）
- 消息推送（sendMessage Bot API）

app_config 必需字段：
- bot_token: Telegram Bot Token（用于消息推送）

app_config 可选字段：
- secret_token: Webhook Secret Token（X-Telegram-Bot-Api-Secret-Token 验证）
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# Telegram Bot API 基地址
_TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramAdapter(ChannelAdapter):
    """Telegram Bot 渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证 Telegram Webhook 请求。

        Telegram 通过 setWebhook 的 secret_token 参数设置签名，
        每次请求在 X-Telegram-Bot-Api-Secret-Token 头部携带。
        """
        secret_token = app_config.get("secret_token", "")
        if not secret_token:
            # 未配置 secret_token 时跳过验证
            return True

        request_token = (
            headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            or headers.get("x-telegram-bot-api-secret-token", "")
        )
        return request_token == secret_token

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """从 Telegram Update JSON 解析消息。

        支持 message 和 channel_post 两种类型。
        仅处理文本消息，忽略其他类型。
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Telegram 消息解析失败: 无效 JSON")
            return None

        # 优先 message，其次 channel_post
        message = data.get("message") or data.get("channel_post")
        if not message:
            return None

        text = message.get("text", "")
        if not text:
            # 忽略非文本消息（图片、贴纸等）
            return None

        # 发送者信息
        sender = message.get("from", {})
        sender_id = str(sender.get("id", message.get("chat", {}).get("id", "")))
        chat_id = str(message.get("chat", {}).get("id", ""))

        return ChannelMessage(
            sender_id=sender_id,
            content=text,
            message_type="text",
            raw_data={
                "update_id": data.get("update_id"),
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
            },
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """Telegram Webhook 无需专门的 URL 验证机制。"""
        return None

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过 Telegram Bot API sendMessage 推送消息。

        Args:
            app_config: 需包含 bot_token。
            recipient_id: chat_id（用户或群组）。
            content: 消息文本。
        """
        bot_token = app_config.get("bot_token", "")
        if not bot_token:
            logger.error("Telegram 推送失败: 未配置 bot_token")
            return False

        url = f"{_TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": recipient_id,
            "text": content,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("ok"):
                        return True
                    logger.warning("Telegram API 返回错误: %s", result.get("description"))
                else:
                    logger.warning("Telegram API HTTP %d", resp.status_code)
                return False
        except httpx.HTTPError as exc:
            logger.error("Telegram 推送异常: %s", exc)
            return False
