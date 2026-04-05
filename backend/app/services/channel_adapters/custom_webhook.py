"""自定义 Webhook 渠道适配器。

提供通用的 HTTP Webhook 接入能力，支持：
- 可配置的 HMAC 签名验证（SHA256/SHA1/MD5）
- 通用 JSON 消息解析（可配置字段映射）
- 消息推送到指定 Webhook URL

适用于没有专用 SDK 的 IM 平台或自建系统。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# 支持的签名算法
_HASH_ALGORITHMS = {
    "sha256": hashlib.sha256,
    "sha1": hashlib.sha1,
    "md5": hashlib.md5,
}


class CustomWebhookAdapter(ChannelAdapter):
    """自定义 Webhook 渠道适配器。

    app_config 配置项：
    - secret: （可选）HMAC 签名密钥
    - sign_algorithm: 签名算法，默认 sha256（支持 sha256/sha1/md5）
    - sign_header: 签名所在的请求头名称，默认 X-Signature
    - sender_field: JSON 中发送者 ID 字段路径，默认 sender_id
    - content_field: JSON 中消息内容字段路径，默认 content
    - type_field: JSON 中消息类型字段路径，默认 message_type
    - webhook_url: 消息推送目标 URL
    """

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证 HMAC 签名。"""
        secret = app_config.get("secret", "")
        if not secret:
            return True

        algorithm = app_config.get("sign_algorithm", "sha256")
        sign_header = app_config.get("sign_header", "x-signature")

        # 请求头名称统一小写
        lower_headers = {k.lower(): v for k, v in headers.items()}
        signature = lower_headers.get(sign_header.lower(), "")
        if not signature:
            return False

        hash_func = _HASH_ALGORITHMS.get(algorithm)
        if not hash_func:
            logger.warning("不支持的签名算法: %s", algorithm)
            return False

        expected = hmac.new(
            secret.encode("utf-8"), body, hash_func
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """从 JSON 请求体中提取消息字段。

        字段路径通过 app_config 配置，支持嵌套（用 . 分隔）。
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("自定义 Webhook 消息解析失败：无效 JSON")
            return None

        sender_field = app_config.get("sender_field", "sender_id")
        content_field = app_config.get("content_field", "content")
        type_field = app_config.get("type_field", "message_type")

        sender_id = _extract_field(data, sender_field)
        content = _extract_field(data, content_field)

        if not sender_id or content is None:
            return None

        message_type = _extract_field(data, type_field) or "text"

        return ChannelMessage(
            sender_id=str(sender_id),
            content=str(content),
            message_type=str(message_type),
            raw_data=data,
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """自定义 Webhook 不需要 URL 验证。"""
        return None

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """向配置的 Webhook URL 推送消息。"""
        webhook_url = app_config.get("webhook_url", "")
        if not webhook_url:
            logger.error("自定义 Webhook 未配置 webhook_url")
            return False

        payload = {
            "recipient_id": recipient_id,
            "content": content,
            "message_type": "text",
        }

        # 如果配置了签名，添加签名头
        headers: dict[str, str] = {"Content-Type": "application/json"}
        secret = app_config.get("secret", "")
        if secret:
            algorithm = app_config.get("sign_algorithm", "sha256")
            hash_func = _HASH_ALGORITHMS.get(algorithm, hashlib.sha256)
            body_bytes = json.dumps(payload).encode("utf-8")
            sig = hmac.new(
                secret.encode("utf-8"), body_bytes, hash_func
            ).hexdigest()
            sign_header = app_config.get("sign_header", "X-Signature")
            headers[sign_header] = sig

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    logger.error(
                        "自定义 Webhook 推送失败: status=%d, body=%s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return False
                return True
        except httpx.HTTPError as exc:
            logger.error("自定义 Webhook 推送网络错误: %s", exc)
            return False


def _extract_field(data: dict[str, Any], field_path: str) -> Any:
    """从嵌套字典中按点分路径提取字段值。

    例如：_extract_field({"a": {"b": "v"}}, "a.b") → "v"
    """
    parts = field_path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current
