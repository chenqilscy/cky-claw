"""钉钉（DingTalk）渠道适配器。

钉钉机器人回调机制：
- 签名验证：timestamp + "\\n" + secret → HMAC-SHA256 → Base64
- 消息接收：POST JSON 格式，包含 text/content、senderNick、senderId 等
- 消息推送：POST 到群机器人 Webhook URL，JSON 格式

app_config 必需字段：
- app_secret: 机器人密钥（用于签名验证）
- webhook_url: 机器人 Webhook 地址（用于推送消息）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class DingTalkAdapter(ChannelAdapter):
    """钉钉渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证钉钉机器人回调签名。

        钉钉签名算法：
        1. 从 header 获取 timestamp 和 sign
        2. 用 timestamp + "\\n" + app_secret 计算 HMAC-SHA256
        3. Base64 编码后比对
        """
        app_secret = app_config.get("app_secret", "")
        if not app_secret:
            # 未配置密钥，跳过签名验证
            return True

        timestamp = headers.get("timestamp", "")
        sign = headers.get("sign", "")

        if not timestamp or not sign:
            return False

        # 验证时间戳新鲜度（5 分钟内）
        try:
            ts = int(timestamp)
            now = int(time.time() * 1000)
            if abs(now - ts) > 300_000:
                logger.warning("钉钉签名时间戳过期: ts=%s, now=%s", timestamp, now)
                return False
        except ValueError:
            return False

        # 计算签名
        string_to_sign = f"{timestamp}\n{app_secret}"
        hmac_code = hmac.new(
            app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode("utf-8")

        return hmac.compare_digest(sign, expected_sign)

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """解析钉钉 JSON 消息。

        钉钉消息格式示例：
        {
            "msgtype": "text",
            "text": {"content": "你好"},
            "senderNick": "张三",
            "senderId": "dingtalk_user_123",
            "conversationId": "cid_xxx",
            "msgId": "msg_xxx",
            ...
        }
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            logger.warning("钉钉消息 JSON 解析失败")
            return None

        msg_type = data.get("msgtype", "text")
        sender_id = data.get("senderId", data.get("senderStaffId", ""))

        if msg_type == "text":
            text_obj = data.get("text", {})
            content = text_obj.get("content", "").strip()
        else:
            # 非文本消息，记录但不处理
            content = f"[{msg_type}]"

        if not sender_id:
            return None

        return ChannelMessage(
            sender_id=sender_id,
            content=content,
            message_type=msg_type,
            raw_data=data,
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """钉钉无 URL 验证机制，始终返回 None。"""
        return None

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过钉钉 Webhook 推送消息。

        钉钉群机器人使用 Webhook URL 推送，消息会发到群里。
        对于单聊机器人，需使用应用内机器人 API（后续扩展）。
        """
        webhook_url = app_config.get("webhook_url", "")
        if not webhook_url:
            logger.error("钉钉 Webhook URL 未配置")
            return False

        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }

        # 如果配置了签名密钥，需在 URL 上附加签名
        app_secret = app_config.get("app_secret", "")
        if app_secret:
            timestamp = str(int(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{app_secret}"
            hmac_code = hmac.new(
                app_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.error("钉钉消息推送失败: %s", data.get("errmsg", ""))
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("钉钉消息推送网络异常: %s", exc)
            return False
