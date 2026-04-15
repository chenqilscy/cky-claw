"""Slack IM 渠道适配器。

实现 Slack Events API 消息接入：
- 请求签名验证（HMAC-SHA256 + 时间戳防重放）
- 消息解析（JSON event_callback → ChannelMessage）
- URL 验证回调（challenge 回显）
- 消息推送（chat.postMessage Web API）

Slack 签名验证规则：
1. 从请求头提取 X-Slack-Request-Timestamp 和 X-Slack-Signature
2. 校验时间戳在 5 分钟（300 秒）内防止重放攻击
3. 构造签名基线：v0:{timestamp}:{body}
4. 计算 HMAC-SHA256：v0=hmac_sha256(signing_secret, sig_basestring)
5. 与 X-Slack-Signature 对比

app_config 必需字段：
- signing_secret: Slack App Signing Secret（签名验证）
- bot_token: Bot User OAuth Token（xoxb-...，消息推送）

app_config 可选字段：
- timestamp_tolerance: 时间戳容差秒数（默认 300）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# Slack Web API 基地址
_SLACK_API_BASE = "https://slack.com/api"

# 需忽略的消息子类型（系统事件、bot 消息等）
_IGNORED_SUBTYPES = frozenset({
    "bot_message",
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "group_join",
    "group_leave",
    "group_topic",
    "group_purpose",
    "group_name",
    "group_archive",
    "group_unarchive",
})


class SlackAdapter(ChannelAdapter):
    """Slack 渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证 Slack 请求签名（HMAC-SHA256 + 时间戳防重放）。

        Slack 签名：v0=hmac_sha256(signing_secret, "v0:{timestamp}:{body}")
        """
        signing_secret = app_config.get("signing_secret", "")
        if not signing_secret:
            return False

        # 从 headers 提取（Slack 使用小写 header 名）
        slack_signature = (
            headers.get("X-Slack-Signature", "")
            or headers.get("x-slack-signature", "")
        )
        timestamp_str = (
            headers.get("X-Slack-Request-Timestamp", "")
            or headers.get("x-slack-request-timestamp", "")
        )

        if not slack_signature or not timestamp_str:
            return False

        # 时间戳防重放攻击
        try:
            request_timestamp = int(timestamp_str)
        except (ValueError, TypeError):
            return False

        tolerance = int(app_config.get("timestamp_tolerance", 300))
        if abs(time.time() - request_timestamp) > tolerance:
            logger.warning("Slack 请求时间戳超出容差: %s", timestamp_str)
            return False

        # 计算签名
        sig_basestring = f"v0:{timestamp_str}:{body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, slack_signature)

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """解析 Slack event_callback 消息。

        仅处理 type=event_callback 且 event.type=message 的用户消息。
        忽略 bot 消息和系统子类型，避免消息循环。
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Slack 消息 JSON 解析失败")
            return None

        # 只处理 event_callback 类型
        if data.get("type") != "event_callback":
            return None

        event = data.get("event", {})
        event_type = event.get("type", "")

        if event_type != "message":
            # 非 message 事件（如 app_mention、reaction_added 等），按事件处理
            return ChannelMessage(
                sender_id=event.get("user", ""),
                content=f"event:{event_type}",
                message_type="event",
                raw_data=data,
            )

        # 过滤系统子类型和 bot 消息
        subtype = event.get("subtype", "")
        if subtype in _IGNORED_SUBTYPES:
            return None

        # 忽略 bot 自身发送的消息，避免消息循环
        if event.get("bot_id"):
            return None

        sender_id = event.get("user", "")
        if not sender_id:
            return None

        content = event.get("text", "")
        channel = event.get("channel", "")

        return ChannelMessage(
            sender_id=sender_id,
            content=content,
            message_type="text",
            raw_data={**data, "_channel": channel},
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理 Slack URL Verification 请求。

        Slack 在配置 Event Subscriptions 时发送 POST：
        {"type": "url_verification", "challenge": "xxx", "token": "xxx"}
        需返回 challenge 值。
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None

        if data.get("type") != "url_verification":
            return None

        challenge = data.get("challenge")
        return str(challenge) if challenge is not None else None

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过 Slack Web API 发送消息。

        使用 chat.postMessage API，recipient_id 可以是频道 ID 或用户 ID。
        """
        bot_token = app_config.get("bot_token", "")
        if not bot_token:
            logger.error("Slack 缺少 bot_token 配置")
            return False

        payload = {
            "channel": recipient_id,
            "text": content,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_SLACK_API_BASE}/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {bot_token}",
                        "Content-Type": "application/json; charset=utf-8",
                    },
                    json=payload,
                )
            data = resp.json()
            if not data.get("ok", False):
                logger.error("Slack 消息发送失败: error=%s", data.get("error", "unknown"))
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Slack 消息发送网络异常: %s", exc)
            return False
