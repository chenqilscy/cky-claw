"""企业微信（WeCom）渠道适配器。

企业微信回调机制：
- URL 验证：GET 请求，带 msg_signature/timestamp/nonce/echostr → 解密 echostr 后返回明文
- 消息接收：POST 请求，XML 格式 → 解密后解析 XML → 提取消息
- 消息推送：POST https://qyapi.weixin.qq.com/cgi-bin/message/send

app_config 必需字段：
- corpid: 企业 ID
- corpsecret: 应用密钥
- token: 回调 Token（用于签名验证）
- encoding_aes_key: 回调 EncodingAESKey（用于消息加解密）
- agent_id: 企业应用 AgentId（企微内部的应用 ID）
"""

from __future__ import annotations

import base64
import hashlib
import logging
import socket
import struct
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

# 企微 API 基地址
_WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"


class WeComAdapter(ChannelAdapter):
    """企业微信渠道适配器。"""

    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证企微回调签名。

        企微签名算法：sha1(sort([token, timestamp, nonce, encrypt_msg]))
        """
        token = app_config.get("token", "")
        # 从 query string 中提取（由 API 层传入 headers 中的自定义字段）
        msg_signature = headers.get("msg_signature", "")
        timestamp = headers.get("timestamp", "")
        nonce = headers.get("nonce", "")

        # 从 XML body 中提取 Encrypt 字段
        encrypt_msg = ""
        try:
            root = ET.fromstring(body)
            encrypt_node = root.find("Encrypt")
            if encrypt_node is not None and encrypt_node.text:
                encrypt_msg = encrypt_node.text
        except ET.ParseError:
            return False

        # 计算签名
        sort_list = sorted([token, timestamp, nonce, encrypt_msg])
        sha1 = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
        return sha1 == msg_signature

    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """解析企微加密 XML 消息。"""
        encoding_aes_key = app_config.get("encoding_aes_key", "")
        corpid = app_config.get("corpid", "")

        try:
            root = ET.fromstring(body)
            encrypt_node = root.find("Encrypt")
            if encrypt_node is None or not encrypt_node.text:
                return None

            # 解密
            plaintext = _decrypt_message(encrypt_node.text, encoding_aes_key, corpid)
            if plaintext is None:
                return None

            # 解析解密后的 XML
            msg_root = ET.fromstring(plaintext)
            msg_type = _get_text(msg_root, "MsgType", "text")
            from_user = _get_text(msg_root, "FromUserName", "")
            content = _get_text(msg_root, "Content", "")

            if msg_type == "event":
                # 事件消息（关注/菜单等），不作为用户消息处理
                return None

            return ChannelMessage(
                sender_id=from_user,
                content=content,
                message_type=msg_type,
                raw_data=_xml_to_dict(msg_root),
            )
        except (ET.ParseError, ValueError) as exc:
            logger.warning("企微消息解析失败: %s", exc)
            return None

    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理企微 URL 验证回调。

        企微在配置回调 URL 时发送 GET 请求，带 echostr 参数（加密内容），需解密后返回。
        """
        echostr = query_params.get("echostr")
        if echostr is None:
            return None

        encoding_aes_key = app_config.get("encoding_aes_key", "")
        corpid = app_config.get("corpid", "")

        result = _decrypt_message(echostr, encoding_aes_key, corpid)
        return result

    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """通过企微 API 推送应用消息。"""
        access_token = await _get_access_token(
            app_config.get("corpid", ""),
            app_config.get("corpsecret", ""),
        )
        if not access_token:
            return False

        wecom_agent_id = app_config.get("agent_id", "")
        payload = {
            "touser": recipient_id,
            "msgtype": "text",
            "agentid": wecom_agent_id,
            "text": {"content": content},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_WECOM_API_BASE}/message/send",
                    params={"access_token": access_token},
                    json=payload,
                )
            data = resp.json()
            if data.get("errcode", 0) != 0:
                logger.error("企微消息推送失败: %s", data.get("errmsg", ""))
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("企微消息推送网络异常: %s", exc)
            return False


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


def _decrypt_message(
    encrypt_text: str, encoding_aes_key: str, corpid: str
) -> str | None:
    """企微消息解密（AES-256-CBC + PKCS7）。

    密文结构：random(16) + msg_len(4, big-endian) + msg + receiveid
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

        # 解析：16 字节随机数 + 4 字节消息长度 + 消息 + CorpID
        msg_len = struct.unpack("!I", content[16:20])[0]
        msg = content[20:20 + msg_len].decode("utf-8")
        receive_id = content[20 + msg_len:].decode("utf-8")

        if receive_id != corpid:
            logger.warning("企微消息 CorpID 不匹配: expected=%s, got=%s", corpid, receive_id)
            return None

        return msg
    except Exception as exc:
        logger.error("企微消息解密失败: %s", exc)
        return None


def _encrypt_message(
    msg: str, encoding_aes_key: str, corpid: str
) -> str | None:
    """企微消息加密（AES-256-CBC + PKCS7）。"""
    if not encoding_aes_key:
        return None

    try:
        aes_key = base64.b64decode(encoding_aes_key + "=")
        iv = aes_key[:16]

        # 构造明文：random(16) + msg_len(4) + msg + corpid
        random_bytes = _generate_random_bytes(16)
        msg_bytes = msg.encode("utf-8")
        corpid_bytes = corpid.encode("utf-8")
        content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + corpid_bytes

        # PKCS7 填充
        padder = PKCS7(128).padder()
        padded = padder.update(content) + padder.finalize()

        # AES 加密
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()

        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as exc:
        logger.error("企微消息加密失败: %s", exc)
        return None


def _generate_random_bytes(length: int) -> bytes:
    """生成随机字节。"""
    import os
    return os.urandom(length)


async def _get_access_token(corpid: str, corpsecret: str) -> str | None:
    """获取企微 access_token。

    TODO: 加入 Redis 缓存（有效期 7200 秒）。
    """
    if not corpid or not corpsecret:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_WECOM_API_BASE}/gettoken",
                params={"corpid": corpid, "corpsecret": corpsecret},
            )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            logger.error("获取企微 access_token 失败: %s", data.get("errmsg", ""))
            return None
        return str(data["access_token"])
    except httpx.HTTPError as exc:
        logger.error("获取企微 access_token 网络异常: %s", exc)
        return None
