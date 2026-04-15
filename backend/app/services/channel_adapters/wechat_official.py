"""微信公众号/服务号渠道适配器。

微信公众平台回调机制：
- URL 验证：GET 请求，带 signature/timestamp/nonce/echostr → 校验签名后直接返回 echostr
- 消息接收：POST 请求，XML 格式 → 明文或加密（取决于配置模式）
- 被动回复：5 秒内 HTTP Response 直接返回 XML 格式回复
- 客服消息推送：POST https://api.weixin.qq.com/cgi-bin/message/custom/send
- 模板消息推送：POST https://api.weixin.qq.com/cgi-bin/message/template/send

签名验证算法（与企业微信不同）：
  sha1(sort([token, timestamp, nonce]))

app_config 必需字段：
- appid: 公众号 AppID
- appsecret: 公众号 AppSecret
- token: 接口配置 Token（用于签名验证）

app_config 可选字段：
- encoding_aes_key: 消息加解密密钥（安全模式/兼容模式需要）
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import struct
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# 微信公众平台 API 基地址
_WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WeChatOfficialAdapter(ChannelAdapter):
    """微信公众号/服务号渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证微信公众号回调签名。

        微信签名算法：sha1(sort([token, timestamp, nonce]))
        注意：与企业微信不同，公众号签名**不包含**消息体加密内容。
        """
        token = app_config.get("token", "")
        signature = headers.get("signature", "")
        timestamp = headers.get("timestamp", "")
        nonce = headers.get("nonce", "")

        if not signature or not timestamp or not nonce:
            return False

        # 按字典序排序后拼接，计算 SHA1
        sort_list = sorted([token, timestamp, nonce])
        expected = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
        return expected == signature

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """解析微信公众号消息（明文 XML 或加密 XML）。

        支持消息类型：text / image / voice / video / shortvideo / location / link / event
        """
        encoding_aes_key = app_config.get("encoding_aes_key", "")
        appid = app_config.get("appid", "")

        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            logger.warning("微信消息 XML 解析失败: %s", exc)
            return None

        # 检查是否为加密消息
        encrypt_node = root.find("Encrypt")
        if encrypt_node is not None and encrypt_node.text and encoding_aes_key:
            # 安全模式 / 兼容模式：解密消息
            plaintext = _decrypt_message(encrypt_node.text, encoding_aes_key, appid)
            if plaintext is None:
                return None
            try:
                root = ET.fromstring(plaintext)
            except ET.ParseError as exc:
                logger.warning("微信解密后消息解析失败: %s", exc)
                return None

        msg_type = _get_text(root, "MsgType", "text")
        from_user = _get_text(root, "FromUserName", "")
        to_user = _get_text(root, "ToUserName", "")

        if msg_type == "event":
            # 事件消息：关注/取消关注/菜单点击等
            event_type = _get_text(root, "Event", "")
            return ChannelMessage(
                sender_id=from_user,
                content=f"event:{event_type}",
                message_type="event",
                raw_data={**_xml_to_dict(root), "_to_user": to_user},
            )

        # 按消息类型提取内容
        content = _extract_content(root, msg_type)

        return ChannelMessage(
            sender_id=from_user,
            content=content,
            message_type=msg_type,
            raw_data={**_xml_to_dict(root), "_to_user": to_user},
        )

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理微信公众号 URL 验证请求。

        微信在配置服务器 URL 时发送 GET 请求，带 echostr 参数。
        验证签名通过后直接返回 echostr（无需解密）。
        """
        echostr = query_params.get("echostr")
        if echostr is None:
            return None

        # 签名验证应由 verify_request 完成，此处只负责返回 echostr
        return echostr

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过客服消息 API 向用户推送文本消息。

        注意：用户需在 48 小时内与公众号有过交互，否则推送会失败。
        """
        access_token = await _get_access_token(
            app_config.get("appid", ""),
            app_config.get("appsecret", ""),
        )
        if not access_token:
            return False

        payload = {
            "touser": recipient_id,
            "msgtype": "text",
            "text": {"content": content},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_WECHAT_API_BASE}/message/custom/send",
                    params={"access_token": access_token},
                    json=payload,
                )
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.error("微信客服消息推送失败: errcode=%s, errmsg=%s",
                             data.get("errcode"), data.get("errmsg", ""))
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("微信客服消息推送网络异常: %s", exc)
            return False

    async def send_template_message(
        self,
        app_config: dict[str, Any],
        recipient_id: str,
        template_id: str,
        data: dict[str, Any],
        url: str = "",
    ) -> bool:
        """发送模板消息。

        Args:
            app_config: 公众号配置。
            recipient_id: 接收者 OpenID。
            template_id: 模板 ID。
            data: 模板数据，格式 {"key": {"value": "xxx", "color": "#173177"}}。
            url: 点击消息跳转的 URL（可选）。

        Returns:
            发送是否成功。
        """
        access_token = await _get_access_token(
            app_config.get("appid", ""),
            app_config.get("appsecret", ""),
        )
        if not access_token:
            return False

        payload: dict[str, Any] = {
            "touser": recipient_id,
            "template_id": template_id,
            "data": data,
        }
        if url:
            payload["url"] = url

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_WECHAT_API_BASE}/message/template/send",
                    params={"access_token": access_token},
                    json=payload,
                )
            result = resp.json()
            if result.get("errcode", 0) != 0:
                logger.error("微信模板消息发送失败: errcode=%s, errmsg=%s",
                             result.get("errcode"), result.get("errmsg", ""))
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("微信模板消息发送网络异常: %s", exc)
            return False


def build_passive_reply(content: str, to_user: str, from_user: str) -> str:
    """构造被动回复 XML（文本消息）。

    微信要求在 5 秒内同步返回 XML 格式的被动回复。
    Webhook 端点可调用此方法生成响应体。

    Args:
        content: 回复文本内容。
        to_user: 接收方 OpenID（原消息的 FromUserName）。
        from_user: 回复方（公众号原始 ID，原消息的 ToUserName）。

    Returns:
        XML 格式的被动回复字符串。
    """
    timestamp = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{timestamp}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


# ==================== 内部工具函数 ====================


def _get_text(element: ET.Element, tag: str, default: str = "") -> str:
    """安全获取 XML 子元素文本。"""
    node = element.find(tag)
    if node is not None and node.text:
        return node.text
    return default


def _xml_to_dict(element: ET.Element) -> dict[str, Any]:
    """将 XML Element 转为扁平 dict（仅取直接子元素文本）。"""
    result: dict[str, Any] = {}
    for child in element:
        result[child.tag] = child.text or ""
    return result


def _extract_content(root: ET.Element, msg_type: str) -> str:
    """按消息类型提取主要内容字段。"""
    if msg_type == "text":
        return _get_text(root, "Content", "")
    if msg_type == "image":
        return _get_text(root, "PicUrl", "")
    if msg_type == "voice":
        # 如果开启了语音识别，Recognition 包含识别结果
        recognition = _get_text(root, "Recognition", "")
        return recognition if recognition else _get_text(root, "MediaId", "")
    if msg_type == "video" or msg_type == "shortvideo":
        return _get_text(root, "MediaId", "")
    if msg_type == "location":
        lat = _get_text(root, "Location_X", "")
        lng = _get_text(root, "Location_Y", "")
        label = _get_text(root, "Label", "")
        return f"{lat},{lng} {label}".strip()
    if msg_type == "link":
        title = _get_text(root, "Title", "")
        url = _get_text(root, "Url", "")
        return f"{title} {url}".strip()
    return ""


def _decrypt_message(
    encrypt_text: str, encoding_aes_key: str, appid: str
) -> str | None:
    """微信公众号消息解密（AES-256-CBC + PKCS7）。

    密文结构：random(16) + msg_len(4, big-endian) + msg + appid
    与企微格式一致，但 receiveid 改为 appid。
    """
    if not encoding_aes_key:
        return None

    try:
        aes_key = base64.b64decode(encoding_aes_key + "=")
        iv = aes_key[:16]

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        encrypted = base64.b64decode(encrypt_text)
        padded = decryptor.update(encrypted) + decryptor.finalize()

        # PKCS7 去填充
        unpadder = PKCS7(128).unpadder()
        content = unpadder.update(padded) + unpadder.finalize()

        # 解析：16 字节随机数 + 4 字节消息长度 + 消息 + AppID
        msg_len = struct.unpack("!I", content[16:20])[0]
        msg = content[20:20 + msg_len].decode("utf-8")
        receive_id = content[20 + msg_len:].decode("utf-8")

        if receive_id != appid:
            logger.warning("微信消息 AppID 不匹配: expected=%s, got=%s", appid, receive_id)
            return None

        return msg
    except Exception as exc:
        logger.error("微信消息解密失败: %s", exc)
        return None


async def _get_access_token(appid: str, appsecret: str) -> str | None:
    """获取微信公众号 access_token（Redis 缓存，TTL 7000 秒）。"""
    if not appid or not appsecret:
        return None

    from app.services.token_cache import get_or_fetch

    async def _fetch() -> str | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_WECHAT_API_BASE}/token",
                    params={
                        "grant_type": "client_credential",
                        "appid": appid,
                        "secret": appsecret,
                    },
                )
            data = resp.json()
            if "access_token" not in data:
                logger.error("获取微信 access_token 失败: %s", data.get("errmsg", ""))
                return None
            return str(data["access_token"])
        except httpx.HTTPError as exc:
            logger.error("获取微信 access_token 网络异常: %s", exc)
            return None

    return await get_or_fetch(f"wechat:{appid}", _fetch)


def _generate_random_bytes(length: int) -> bytes:
    """生成随机字节。"""
    return os.urandom(length)
