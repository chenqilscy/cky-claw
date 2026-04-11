"""飞书 IM 渠道适配器。

实现飞书开放平台的：
- 请求签名验证（HMAC-SHA256）
- 消息解析（JSON → ChannelMessage）
- URL 验证回调（challenge 回显）
- 消息推送（调用飞书 REST API）

飞书签名规则：
1. 将 timestamp + nonce + encrypt_key 拼接为字符串
2. 计算 SHA256 哈希
3. 与请求头中的 X-Lark-Signature 比对
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


class FeishuAdapter(ChannelAdapter):
    """飞书渠道适配器。

    app_config 需包含：
    - verification_token: 飞书应用的 Verification Token
    - encrypt_key: （可选）加密密钥，用于签名验证
    - app_id: 飞书应用 App ID
    - app_secret: 飞书应用 App Secret
    """

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证飞书请求的签名。

        飞书使用 encrypt_key 进行签名验证：
        sha256(timestamp + nonce + encrypt_key + body)
        """
        encrypt_key = app_config.get("encrypt_key", "")
        if not encrypt_key:
            # 未配置加密密钥，跳过签名验证
            return True

        timestamp = headers.get("x-lark-request-timestamp", "")
        nonce = headers.get("x-lark-request-nonce", "")
        signature = headers.get("x-lark-signature", "")

        if not (timestamp and nonce and signature):
            return False

        # 飞书签名算法：sha256(timestamp + nonce + encrypt_key + body)
        content = timestamp + nonce + encrypt_key + body.decode("utf-8")
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """解析飞书推送的事件消息。

        飞书消息格式（EventV2）：
        {
          "schema": "2.0",
          "header": {"event_type": "im.message.receive_v1", ...},
          "event": {
            "sender": {"sender_id": {"open_id": "ou_xxx"}},
            "message": {"message_type": "text", "content": "{\"text\":\"hello\"}"}
          }
        }
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("飞书消息解析失败：无效 JSON")
            return None

        # URL 验证请求不是消息
        if "challenge" in data:
            return None

        # EventV2 格式
        event = data.get("event", {})
        header = data.get("header", {})
        event_type = header.get("event_type", "")

        # 只处理消息接收事件
        if event_type != "im.message.receive_v1":
            return None

        sender = event.get("sender", {})
        sender_id_obj = sender.get("sender_id", {})
        sender_id = sender_id_obj.get("open_id", "")

        message = event.get("message", {})
        message_type = message.get("message_type", "text")

        # 解析消息内容
        content_str = message.get("content", "{}")
        try:
            content_data = json.loads(content_str)
        except json.JSONDecodeError:
            content_data = {"text": content_str}

        content = content_data.get("text", "")

        if not sender_id:
            return None

        return ChannelMessage(
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            raw_data=data,
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理飞书 URL 验证回调。

        飞书发送 {"challenge": "xxx", "token": "xxx", "type": "url_verification"}
        需返回 {"challenge": "xxx"}
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if data.get("type") != "url_verification":
            return None

        challenge = data.get("challenge", "")
        if not challenge:
            return None

        # 验证 token
        verification_token = app_config.get("verification_token", "")
        if verification_token and data.get("token") != verification_token:
            logger.warning("飞书 URL 验证 token 不匹配")
            return None

        return json.dumps({"challenge": challenge})

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """向飞书用户发送消息。

        使用飞书 REST API 发送消息，需先获取 tenant_access_token。

        Args:
            app_config: 需包含 app_id 和 app_secret。
            recipient_id: 飞书用户 open_id。
            content: 消息文本。
        """
        access_token = await self._get_tenant_access_token(app_config)
        if not access_token:
            return False

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "open_id"}
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "receive_id": recipient_id,
            "msg_type": "text",
            "content": json.dumps({"text": content}),
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, params=params, headers=headers, json=payload
                )
                result = resp.json()
                if result.get("code") != 0:
                    logger.error("飞书消息发送失败: %s", result.get("msg", "unknown"))
                    return False
                return True
        except httpx.HTTPError as exc:
            logger.error("飞书消息发送网络错误: %s", exc)
            return False

    async def _get_tenant_access_token(
        self, app_config: dict[str, Any]
    ) -> str | None:
        """获取飞书 tenant_access_token（Redis 缓存，TTL 7000 秒）。"""
        app_id = app_config.get("app_id", "")
        app_secret = app_config.get("app_secret", "")
        if not (app_id and app_secret):
            logger.error("飞书配置缺少 app_id 或 app_secret")
            return None

        from app.services.token_cache import get_or_fetch

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": app_id, "app_secret": app_secret}

        async def _fetch() -> str | None:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json=payload)
                    result = resp.json()
                    if result.get("code") != 0:
                        logger.error(
                            "获取飞书 tenant_access_token 失败: %s",
                            result.get("msg", "unknown"),
                        )
                        return None
                    return result.get("tenant_access_token")  # type: ignore[no-any-return]
            except httpx.HTTPError as exc:
                logger.error("获取飞书 token 网络错误: %s", exc)
                return None

        return await get_or_fetch(f"feishu:{app_id}", _fetch)
