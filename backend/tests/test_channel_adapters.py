"""多渠道接入 ChannelAdapter 单元测试。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

import httpx


# ========== ChannelAdapter 基础架构 ==========


class TestChannelAdapterBase:
    """适配器抽象基类和注册表。"""

    def test_channel_message_dataclass(self) -> None:
        """ChannelMessage 数据类正确创建。"""
        from app.services.channel_adapters.base import ChannelMessage

        msg = ChannelMessage(sender_id="user1", content="hello")
        assert msg.sender_id == "user1"
        assert msg.content == "hello"
        assert msg.message_type == "text"
        assert msg.raw_data == {}

    def test_channel_message_with_all_fields(self) -> None:
        """ChannelMessage 所有字段。"""
        from app.services.channel_adapters.base import ChannelMessage

        msg = ChannelMessage(
            sender_id="u2",
            content="img",
            message_type="image",
            raw_data={"url": "https://example.com/img.png"},
        )
        assert msg.message_type == "image"
        assert msg.raw_data["url"] == "https://example.com/img.png"

    def test_get_adapter_wecom(self) -> None:
        """get_adapter 返回 WeComAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.wecom import WeComAdapter

        adapter = get_adapter("wecom")
        assert isinstance(adapter, WeComAdapter)

    def test_get_adapter_dingtalk(self) -> None:
        """get_adapter 返回 DingTalkAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.dingtalk import DingTalkAdapter

        adapter = get_adapter("dingtalk")
        assert isinstance(adapter, DingTalkAdapter)

    def test_get_adapter_feishu(self) -> None:
        """get_adapter 返回 FeishuAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.feishu import FeishuAdapter

        adapter = get_adapter("feishu")
        assert isinstance(adapter, FeishuAdapter)

    def test_get_adapter_custom_webhook(self) -> None:
        """get_adapter 返回 CustomWebhookAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.custom_webhook import CustomWebhookAdapter

        adapter = get_adapter("custom_webhook")
        assert isinstance(adapter, CustomWebhookAdapter)

    def test_get_adapter_unknown(self) -> None:
        """未知渠道类型返回 None。"""
        from app.services.channel_adapters import get_adapter

        assert get_adapter("unknown") is None
        assert get_adapter("telegram") is None

    def test_adapter_registry_exports(self) -> None:
        """__init__ 导出完整。"""
        from app.services.channel_adapters import (
            ChannelAdapter,
            ChannelMessage,
            CustomWebhookAdapter,
            DingTalkAdapter,
            FeishuAdapter,
            WeComAdapter,
            get_adapter,
        )

        assert ChannelAdapter is not None
        assert ChannelMessage is not None


# ========== WeComAdapter 测试 ==========


def _wecom_encrypt(msg: str, encoding_aes_key: str, corpid: str) -> str:
    """辅助：企微消息加密。"""
    import os

    aes_key = base64.b64decode(encoding_aes_key + "=")
    iv = aes_key[:16]
    random_bytes = os.urandom(16)
    msg_bytes = msg.encode("utf-8")
    corpid_bytes = corpid.encode("utf-8")
    content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + corpid_bytes

    padder = PKCS7(128).padder()
    padded = padder.update(content) + padder.finalize()

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def _wecom_sign(token: str, timestamp: str, nonce: str, encrypt_text: str) -> str:
    """辅助：企微签名计算。"""
    sort_list = sorted([token, timestamp, nonce, encrypt_text])
    return hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()


# 标准测试配置
_WECOM_TOKEN = "test_token_123"
_WECOM_CORPID = "wx_corp_test_id"
_WECOM_AES_KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode("utf-8").rstrip("=")
_WECOM_CONFIG: dict[str, Any] = {
    "corpid": _WECOM_CORPID,
    "corpsecret": "test_secret",
    "token": _WECOM_TOKEN,
    "encoding_aes_key": _WECOM_AES_KEY,
    "agent_id": "1000001",
}


class TestWeComAdapter:
    """企业微信适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.wecom import WeComAdapter
        return WeComAdapter()

    def test_verify_request_valid(self) -> None:
        """有效签名通过验证。"""
        adapter = self._get_adapter()

        msg_xml = "<xml><Content>hello</Content></xml>"
        encrypt_text = _wecom_encrypt(msg_xml, _WECOM_AES_KEY, _WECOM_CORPID)
        timestamp = "1234567890"
        nonce = "test_nonce"
        signature = _wecom_sign(_WECOM_TOKEN, timestamp, nonce, encrypt_text)

        body = f"<xml><Encrypt><![CDATA[{encrypt_text}]]></Encrypt></xml>".encode()
        headers = {
            "msg_signature": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        }

        assert adapter.verify_request(headers, body, _WECOM_CONFIG) is True

    def test_verify_request_invalid_signature(self) -> None:
        """无效签名不通过验证。"""
        adapter = self._get_adapter()
        body = b"<xml><Encrypt>bad</Encrypt></xml>"
        headers = {
            "msg_signature": "invalid_sig",
            "timestamp": "123",
            "nonce": "abc",
        }
        assert adapter.verify_request(headers, body, _WECOM_CONFIG) is False

    def test_verify_request_invalid_xml(self) -> None:
        """无效 XML 体不通过验证。"""
        adapter = self._get_adapter()
        body = b"not-xml-at-all"
        headers = {"msg_signature": "x", "timestamp": "1", "nonce": "n"}
        assert adapter.verify_request(headers, body, _WECOM_CONFIG) is False

    def test_parse_message_text(self) -> None:
        """解析企微文本消息。"""
        adapter = self._get_adapter()

        msg_xml = (
            "<xml>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<Content><![CDATA[你好 Agent]]></Content>"
            "<MsgId>12345</MsgId>"
            "</xml>"
        )
        encrypt_text = _wecom_encrypt(msg_xml, _WECOM_AES_KEY, _WECOM_CORPID)
        body = f"<xml><Encrypt><![CDATA[{encrypt_text}]]></Encrypt></xml>".encode()

        msg = adapter.parse_message(body, _WECOM_CONFIG)
        assert msg is not None
        assert msg.sender_id == "zhangsan"
        assert msg.content == "你好 Agent"
        assert msg.message_type == "text"

    def test_parse_message_event_returns_none(self) -> None:
        """事件消息返回 None（不作为用户消息处理）。"""
        adapter = self._get_adapter()

        event_xml = (
            "<xml>"
            "<MsgType><![CDATA[event]]></MsgType>"
            "<Event><![CDATA[subscribe]]></Event>"
            "</xml>"
        )
        encrypt_text = _wecom_encrypt(event_xml, _WECOM_AES_KEY, _WECOM_CORPID)
        body = f"<xml><Encrypt><![CDATA[{encrypt_text}]]></Encrypt></xml>".encode()

        msg = adapter.parse_message(body, _WECOM_CONFIG)
        assert msg is None

    def test_parse_message_invalid_body(self) -> None:
        """无效消息体返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not-xml", _WECOM_CONFIG) is None

    def test_parse_message_no_encrypt_node(self) -> None:
        """无 Encrypt 节点返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"<xml></xml>", _WECOM_CONFIG) is None

    def test_handle_verification(self) -> None:
        """URL 验证请求正确解密 echostr。"""
        adapter = self._get_adapter()

        # 加密一个 echostr
        echostr_plain = "echo_test_12345"
        echostr_encrypted = _wecom_encrypt(echostr_plain, _WECOM_AES_KEY, _WECOM_CORPID)

        query_params = {"echostr": echostr_encrypted}
        result = adapter.handle_verification(b"", query_params, _WECOM_CONFIG)
        assert result == echostr_plain

    def test_handle_verification_no_echostr(self) -> None:
        """非验证请求返回 None。"""
        adapter = self._get_adapter()
        result = adapter.handle_verification(b"", {}, _WECOM_CONFIG)
        assert result is None

    def test_handle_verification_no_aes_key(self) -> None:
        """未配置 AES Key 返回 None。"""
        adapter = self._get_adapter()
        result = adapter.handle_verification(b"", {"echostr": "test"}, {"corpid": "x"})
        assert result is None

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """发送消息成功。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"errcode": 0, "access_token": "fake_token"}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        with patch("app.services.channel_adapters.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECOM_CONFIG, "zhangsan", "Agent 回复")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_corpid(self) -> None:
        """未配置 corpid 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "user", "text")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """企微 API 返回错误。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"errcode": 0, "access_token": "tok"}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 60020, "errmsg": "not in whitelist"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        with patch("app.services.channel_adapters.wecom.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECOM_CONFIG, "user", "text")
        assert result is False


# ========== DingTalkAdapter 测试 ==========


_DINGTALK_SECRET = "dingtalk_test_secret_123"
_DINGTALK_CONFIG: dict[str, Any] = {
    "app_secret": _DINGTALK_SECRET,
    "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=test",
}


def _dingtalk_sign(timestamp: str, secret: str) -> str:
    """辅助：钉钉签名计算。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


class TestDingTalkAdapter:
    """钉钉适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.dingtalk import DingTalkAdapter
        return DingTalkAdapter()

    def test_verify_request_valid(self) -> None:
        """有效签名通过验证。"""
        adapter = self._get_adapter()
        timestamp = str(int(time.time() * 1000))
        sign = _dingtalk_sign(timestamp, _DINGTALK_SECRET)

        headers = {"timestamp": timestamp, "sign": sign}
        assert adapter.verify_request(headers, b"{}", _DINGTALK_CONFIG) is True

    def test_verify_request_invalid_sign(self) -> None:
        """无效签名不通过。"""
        adapter = self._get_adapter()
        ts = str(int(time.time() * 1000))
        headers = {"timestamp": ts, "sign": "bad_sign"}
        assert adapter.verify_request(headers, b"{}", _DINGTALK_CONFIG) is False

    def test_verify_request_expired_timestamp(self) -> None:
        """过期时间戳不通过（5 分钟以上）。"""
        adapter = self._get_adapter()
        old_ts = str(int((time.time() - 600) * 1000))  # 10 分钟前
        sign = _dingtalk_sign(old_ts, _DINGTALK_SECRET)
        headers = {"timestamp": old_ts, "sign": sign}
        assert adapter.verify_request(headers, b"{}", _DINGTALK_CONFIG) is False

    def test_verify_request_no_secret(self) -> None:
        """未配置密钥跳过验证（返回 True）。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b"{}", {}) is True

    def test_verify_request_missing_headers(self) -> None:
        """缺少签名头不通过。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b"{}", _DINGTALK_CONFIG) is False

    def test_parse_message_text(self) -> None:
        """解析钉钉文本消息。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "msgtype": "text",
            "text": {"content": "你好机器人"},
            "senderId": "dingtalk_user_001",
            "senderNick": "张三",
        }).encode()

        msg = adapter.parse_message(body, _DINGTALK_CONFIG)
        assert msg is not None
        assert msg.sender_id == "dingtalk_user_001"
        assert msg.content == "你好机器人"
        assert msg.message_type == "text"

    def test_parse_message_image(self) -> None:
        """非文本消息返回 [类型] 占位。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "msgtype": "image",
            "senderId": "u1",
        }).encode()
        msg = adapter.parse_message(body, _DINGTALK_CONFIG)
        assert msg is not None
        assert msg.content == "[image]"

    def test_parse_message_no_sender(self) -> None:
        """无 senderId 返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"msgtype": "text", "text": {"content": "hello"}}).encode()
        msg = adapter.parse_message(body, _DINGTALK_CONFIG)
        assert msg is None

    def test_parse_message_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not-json", _DINGTALK_CONFIG) is None

    def test_handle_verification_returns_none(self) -> None:
        """钉钉无 URL 验证机制。"""
        adapter = self._get_adapter()
        assert adapter.handle_verification(b"", {}, _DINGTALK_CONFIG) is None

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """推送消息成功。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.dingtalk.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_DINGTALK_CONFIG, "user1", "回复内容")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_webhook_url(self) -> None:
        """未配置 Webhook URL 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "user", "text")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """钉钉 API 返回错误。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 310000, "errmsg": "keywords not match"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.dingtalk.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_DINGTALK_CONFIG, "user", "text")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_sign(self) -> None:
        """带签名的消息推送。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.dingtalk.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_DINGTALK_CONFIG, "user", "text")
        assert result is True
        # 验证 URL 中包含 timestamp 和 sign
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        assert "timestamp=" in url
        assert "sign=" in url


# ========== Webhook 端点集成测试 ==========


class TestWebhookEndpointWithAdapter:
    """Webhook 端点适配器集成测试。"""

    def test_adapter_used_for_dingtalk(self) -> None:
        """钉钉渠道使用 DingTalkAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.dingtalk import DingTalkAdapter

        adapter = get_adapter("dingtalk")
        assert isinstance(adapter, DingTalkAdapter)

    def test_adapter_used_for_wecom(self) -> None:
        """企微渠道使用 WeComAdapter。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.wecom import WeComAdapter

        adapter = get_adapter("wecom")
        assert isinstance(adapter, WeComAdapter)

    def test_generic_webhook_no_adapter(self) -> None:
        """通用 webhook 类型无适配器。"""
        from app.services.channel_adapters import get_adapter

        assert get_adapter("webhook") is None

    def test_webhook_endpoint_registered(self) -> None:
        """Webhook 端点路由已注册。"""
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert any("webhook" in r for r in routes)


# ========== 加解密工具函数 ==========


class TestWeComCrypto:
    """企微加解密核心函数测试。"""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """加密后解密得到原文。"""
        from app.services.channel_adapters.wecom import _decrypt_message, _encrypt_message

        original = "Hello, 企业微信! 你好世界 🎉"
        encrypted = _encrypt_message(original, _WECOM_AES_KEY, _WECOM_CORPID)
        assert encrypted is not None

        decrypted = _decrypt_message(encrypted, _WECOM_AES_KEY, _WECOM_CORPID)
        assert decrypted == original

    def test_decrypt_wrong_corpid(self) -> None:
        """解密时 CorpID 不匹配返回 None。"""
        from app.services.channel_adapters.wecom import _decrypt_message, _encrypt_message

        encrypted = _encrypt_message("test", _WECOM_AES_KEY, _WECOM_CORPID)
        assert encrypted is not None

        result = _decrypt_message(encrypted, _WECOM_AES_KEY, "wrong_corpid")
        assert result is None

    def test_decrypt_no_aes_key(self) -> None:
        """无 AES Key 返回 None。"""
        from app.services.channel_adapters.wecom import _decrypt_message

        assert _decrypt_message("data", "", "corpid") is None

    def test_encrypt_no_aes_key(self) -> None:
        """无 AES Key 返回 None。"""
        from app.services.channel_adapters.wecom import _encrypt_message

        assert _encrypt_message("msg", "", "corpid") is None

    def test_decrypt_invalid_base64(self) -> None:
        """非法 Base64 解密返回 None。"""
        from app.services.channel_adapters.wecom import _decrypt_message

        result = _decrypt_message("not-valid-base64!!!", _WECOM_AES_KEY, _WECOM_CORPID)
        assert result is None


# ========== 飞书适配器测试 ==========

_FEISHU_CONFIG: dict[str, Any] = {
    "verification_token": "test_verify_token",
    "encrypt_key": "test_encrypt_key_123",
    "app_id": "cli_test_app_id",
    "app_secret": "test_app_secret",
}


def _feishu_sign(timestamp: str, nonce: str, encrypt_key: str, body: str) -> str:
    """计算飞书签名。"""
    content = timestamp + nonce + encrypt_key + body
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestFeishuAdapter:
    """飞书适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.feishu import FeishuAdapter
        return FeishuAdapter()

    def test_verify_request_valid(self) -> None:
        """有效签名验证通过。"""
        adapter = self._get_adapter()
        body = '{"event": {}}'
        ts = "1234567890"
        nonce = "abc123"
        sig = _feishu_sign(ts, nonce, _FEISHU_CONFIG["encrypt_key"], body)
        headers = {
            "x-lark-request-timestamp": ts,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": sig,
        }
        assert adapter.verify_request(headers, body.encode(), _FEISHU_CONFIG) is True

    def test_verify_request_invalid(self) -> None:
        """无效签名验证失败。"""
        adapter = self._get_adapter()
        headers = {
            "x-lark-request-timestamp": "123",
            "x-lark-request-nonce": "abc",
            "x-lark-signature": "wrong_signature",
        }
        assert adapter.verify_request(headers, b'{}', _FEISHU_CONFIG) is False

    def test_verify_request_missing_headers(self) -> None:
        """缺少签名头验证失败。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b'{}', _FEISHU_CONFIG) is False

    def test_verify_request_no_encrypt_key(self) -> None:
        """无 encrypt_key 时跳过验证。"""
        adapter = self._get_adapter()
        config = {"verification_token": "tok"}
        assert adapter.verify_request({}, b'{}', config) is True

    def test_parse_message_text(self) -> None:
        """解析飞书文本消息。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_test_user"}},
                "message": {
                    "message_type": "text",
                    "content": json.dumps({"text": "你好"})
                }
            }
        }).encode()
        msg = adapter.parse_message(body, _FEISHU_CONFIG)
        assert msg is not None
        assert msg.sender_id == "ou_test_user"
        assert msg.content == "你好"
        assert msg.message_type == "text"

    def test_parse_message_challenge(self) -> None:
        """challenge 请求返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"challenge": "abc", "type": "url_verification"}).encode()
        assert adapter.parse_message(body, _FEISHU_CONFIG) is None

    def test_parse_message_non_message_event(self) -> None:
        """非消息事件返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "header": {"event_type": "contact.user.created_v3"},
            "event": {}
        }).encode()
        assert adapter.parse_message(body, _FEISHU_CONFIG) is None

    def test_parse_message_no_sender(self) -> None:
        """无发送者返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {}},
                "message": {"content": '{"text":"hi"}'}
            }
        }).encode()
        assert adapter.parse_message(body, _FEISHU_CONFIG) is None

    def test_parse_message_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not json", _FEISHU_CONFIG) is None

    def test_handle_verification_success(self) -> None:
        """URL 验证成功。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "challenge": "test_challenge_123",
            "token": _FEISHU_CONFIG["verification_token"],
            "type": "url_verification"
        }).encode()
        result = adapter.handle_verification(body, {}, _FEISHU_CONFIG)
        assert result is not None
        data = json.loads(result)
        assert data["challenge"] == "test_challenge_123"

    def test_handle_verification_wrong_token(self) -> None:
        """token 不匹配返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "challenge": "abc",
            "token": "wrong_token",
            "type": "url_verification"
        }).encode()
        assert adapter.handle_verification(body, {}, _FEISHU_CONFIG) is None

    def test_handle_verification_not_verification_type(self) -> None:
        """非验证类型返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"type": "event", "event": {}}).encode()
        assert adapter.handle_verification(body, {}, _FEISHU_CONFIG) is None

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """飞书消息发送成功。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"code": 0, "tenant_access_token": "t-xxx"}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"code": 0, "msg": "success"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=[mock_token_resp, mock_send_resp])

        with patch("app.services.channel_adapters.feishu.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_FEISHU_CONFIG, "ou_user", "hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_app_id(self) -> None:
        """缺少 app_id 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "ou_user", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_token_error(self) -> None:
        """获取 token 失败时发送失败。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 99991, "msg": "invalid app_id"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.feishu.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_FEISHU_CONFIG, "ou_user", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """飞书发送 API 返回错误。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"code": 0, "tenant_access_token": "t-xxx"}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"code": 230001, "msg": "no permission"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=[mock_token_resp, mock_send_resp])

        with patch("app.services.channel_adapters.feishu.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_FEISHU_CONFIG, "ou_user", "hello")
        assert result is False


# ========== 自定义 Webhook 适配器测试 ==========

_CUSTOM_WEBHOOK_CONFIG: dict[str, Any] = {
    "secret": "my_webhook_secret",
    "sign_algorithm": "sha256",
    "sign_header": "x-signature",
    "sender_field": "user.id",
    "content_field": "message.text",
    "type_field": "message.type",
    "webhook_url": "https://example.com/webhook/push",
}


class TestCustomWebhookAdapter:
    """自定义 Webhook 适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.custom_webhook import CustomWebhookAdapter
        return CustomWebhookAdapter()

    def test_verify_request_valid(self) -> None:
        """有效 HMAC 签名验证通过。"""
        adapter = self._get_adapter()
        body = b'{"user": {"id": "u1"}, "message": {"text": "hi"}}'
        sig = hmac.new(
            _CUSTOM_WEBHOOK_CONFIG["secret"].encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        headers = {"X-Signature": sig}
        assert adapter.verify_request(headers, body, _CUSTOM_WEBHOOK_CONFIG) is True

    def test_verify_request_invalid(self) -> None:
        """无效签名验证失败。"""
        adapter = self._get_adapter()
        headers = {"X-Signature": "wrong_sig"}
        assert adapter.verify_request(headers, b'{}', _CUSTOM_WEBHOOK_CONFIG) is False

    def test_verify_request_no_secret(self) -> None:
        """无 secret 跳过签名验证。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b'{}', {}) is True

    def test_verify_request_missing_header(self) -> None:
        """缺少签名头验证失败。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b'{}', _CUSTOM_WEBHOOK_CONFIG) is False

    def test_verify_request_sha1(self) -> None:
        """SHA1 签名算法。"""
        adapter = self._get_adapter()
        config = {**_CUSTOM_WEBHOOK_CONFIG, "sign_algorithm": "sha1"}
        body = b'{"data": true}'
        sig = hmac.new(config["secret"].encode(), body, hashlib.sha1).hexdigest()
        assert adapter.verify_request({"X-Signature": sig}, body, config) is True

    def test_parse_message_nested_fields(self) -> None:
        """解析嵌套字段路径的消息。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "user": {"id": "u123"},
            "message": {"text": "hello world", "type": "text"}
        }).encode()
        msg = adapter.parse_message(body, _CUSTOM_WEBHOOK_CONFIG)
        assert msg is not None
        assert msg.sender_id == "u123"
        assert msg.content == "hello world"
        assert msg.message_type == "text"

    def test_parse_message_flat_fields(self) -> None:
        """解析扁平字段路径的消息。"""
        adapter = self._get_adapter()
        config = {"sender_field": "from", "content_field": "body"}
        body = json.dumps({"from": "user1", "body": "test msg"}).encode()
        msg = adapter.parse_message(body, config)
        assert msg is not None
        assert msg.sender_id == "user1"
        assert msg.content == "test msg"
        assert msg.message_type == "text"  # 默认

    def test_parse_message_missing_sender(self) -> None:
        """缺少发送者返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"message": {"text": "hi"}}).encode()
        assert adapter.parse_message(body, _CUSTOM_WEBHOOK_CONFIG) is None

    def test_parse_message_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not json", _CUSTOM_WEBHOOK_CONFIG) is None

    def test_handle_verification(self) -> None:
        """自定义 Webhook 不需要 URL 验证。"""
        adapter = self._get_adapter()
        assert adapter.handle_verification(b"", {}, _CUSTOM_WEBHOOK_CONFIG) is None

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """推送消息成功。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.custom_webhook.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_CUSTOM_WEBHOOK_CONFIG, "user1", "hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_url(self) -> None:
        """未配置 webhook_url 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_http_error(self) -> None:
        """HTTP 请求异常。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.custom_webhook.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_CUSTOM_WEBHOOK_CONFIG, "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_sign(self) -> None:
        """带签名的消息推送。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.custom_webhook.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_CUSTOM_WEBHOOK_CONFIG, "user1", "hello")
        assert result is True
        # 验证签名头
        call_args = mock_client.post.call_args
        headers = call_args[1].get("headers", {})
        assert "x-signature" in headers


# ========== 微信公众号/服务号适配器测试 ==========

_WECHAT_OFFICIAL_CONFIG: dict[str, Any] = {
    "appid": "wx_test_appid",
    "appsecret": "wx_test_appsecret",
    "token": "wx_verify_token",
}

_WECHAT_OFFICIAL_CONFIG_ENCRYPTED: dict[str, Any] = {
    **_WECHAT_OFFICIAL_CONFIG,
    "encoding_aes_key": base64.b64encode(b"a" * 32).decode().rstrip("="),
}


def _make_wechat_signature(token: str, timestamp: str, nonce: str) -> str:
    """按微信公众号规则生成签名。"""
    sort_list = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()


def _build_text_xml(
    from_user: str, to_user: str, content: str, msg_id: str = "123456"
) -> bytes:
    """构造微信文本消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        f"<MsgId>{msg_id}</MsgId>"
        "</xml>"
    ).encode("utf-8")


def _build_image_xml(from_user: str, to_user: str) -> bytes:
    """构造微信图片消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[image]]></MsgType>"
        "<PicUrl><![CDATA[https://example.com/pic.jpg]]></PicUrl>"
        "<MediaId><![CDATA[media_id_123]]></MediaId>"
        "<MsgId>123457</MsgId>"
        "</xml>"
    ).encode("utf-8")


def _build_voice_xml(from_user: str, to_user: str, recognition: str = "") -> bytes:
    """构造微信语音消息 XML。"""
    create_time = str(int(time.time()))
    recognition_tag = (
        f"<Recognition><![CDATA[{recognition}]]></Recognition>" if recognition else ""
    )
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[voice]]></MsgType>"
        "<MediaId><![CDATA[voice_media_123]]></MediaId>"
        "<Format><![CDATA[amr]]></Format>"
        f"{recognition_tag}"
        "<MsgId>123458</MsgId>"
        "</xml>"
    ).encode("utf-8")


def _build_event_xml(from_user: str, to_user: str, event_type: str) -> bytes:
    """构造微信事件消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[event]]></MsgType>"
        f"<Event><![CDATA[{event_type}]]></Event>"
        "</xml>"
    ).encode("utf-8")


def _build_location_xml(from_user: str, to_user: str) -> bytes:
    """构造微信位置消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[location]]></MsgType>"
        "<Location_X>39.908860</Location_X>"
        "<Location_Y>116.397470</Location_Y>"
        "<Scale>20</Scale>"
        "<Label><![CDATA[天安门广场]]></Label>"
        "<MsgId>123459</MsgId>"
        "</xml>"
    ).encode("utf-8")


def _build_link_xml(from_user: str, to_user: str) -> bytes:
    """构造微信链接消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[link]]></MsgType>"
        "<Title><![CDATA[CkyClaw 官网]]></Title>"
        "<Description><![CDATA[AI Agent 平台]]></Description>"
        "<Url><![CDATA[https://ckyclaw.com]]></Url>"
        "<MsgId>123460</MsgId>"
        "</xml>"
    ).encode("utf-8")


def _build_video_xml(from_user: str, to_user: str, msg_type: str = "video") -> bytes:
    """构造微信视频/短视频消息 XML。"""
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        f"<MsgType><![CDATA[{msg_type}]]></MsgType>"
        "<MediaId><![CDATA[video_media_123]]></MediaId>"
        "<ThumbMediaId><![CDATA[thumb_media_123]]></ThumbMediaId>"
        "<MsgId>123461</MsgId>"
        "</xml>"
    ).encode("utf-8")


class TestWeChatOfficialAdapter:
    """微信公众号/服务号适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.wechat_official import WeChatOfficialAdapter
        return WeChatOfficialAdapter()

    # ---------- 签名验证 ----------

    def test_verify_request_valid(self) -> None:
        """有效签名验证通过。"""
        adapter = self._get_adapter()
        ts, nonce = "1609459200", "abc123"
        sig = _make_wechat_signature(_WECHAT_OFFICIAL_CONFIG["token"], ts, nonce)
        headers = {"signature": sig, "timestamp": ts, "nonce": nonce}
        assert adapter.verify_request(headers, b"", _WECHAT_OFFICIAL_CONFIG) is True

    def test_verify_request_invalid_signature(self) -> None:
        """无效签名验证失败。"""
        adapter = self._get_adapter()
        headers = {"signature": "bad_sig", "timestamp": "123", "nonce": "abc"}
        assert adapter.verify_request(headers, b"", _WECHAT_OFFICIAL_CONFIG) is False

    def test_verify_request_missing_params(self) -> None:
        """缺少签名参数验证失败。"""
        adapter = self._get_adapter()
        # 缺少 signature
        assert adapter.verify_request(
            {"timestamp": "123", "nonce": "abc"}, b"", _WECHAT_OFFICIAL_CONFIG
        ) is False
        # 缺少 timestamp
        assert adapter.verify_request(
            {"signature": "abc", "nonce": "abc"}, b"", _WECHAT_OFFICIAL_CONFIG
        ) is False
        # 缺少 nonce
        assert adapter.verify_request(
            {"signature": "abc", "timestamp": "123"}, b"", _WECHAT_OFFICIAL_CONFIG
        ) is False

    def test_verify_request_empty_headers(self) -> None:
        """空 headers 验证失败。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b"", _WECHAT_OFFICIAL_CONFIG) is False

    # ---------- 消息解析：文本 ----------

    def test_parse_text_message(self) -> None:
        """解析文本消息。"""
        adapter = self._get_adapter()
        body = _build_text_xml("user_openid", "gh_official", "hello world")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.sender_id == "user_openid"
        assert msg.content == "hello world"
        assert msg.message_type == "text"
        assert msg.raw_data["_to_user"] == "gh_official"

    # ---------- 消息解析：图片 ----------

    def test_parse_image_message(self) -> None:
        """解析图片消息。"""
        adapter = self._get_adapter()
        body = _build_image_xml("user1", "gh_official")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "image"
        assert msg.content == "https://example.com/pic.jpg"

    # ---------- 消息解析：语音 ----------

    def test_parse_voice_message_with_recognition(self) -> None:
        """解析语音消息（带语音识别）。"""
        adapter = self._get_adapter()
        body = _build_voice_xml("user1", "gh_official", "你好世界")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "voice"
        assert msg.content == "你好世界"

    def test_parse_voice_message_without_recognition(self) -> None:
        """解析语音消息（无语音识别）。"""
        adapter = self._get_adapter()
        body = _build_voice_xml("user1", "gh_official")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "voice"
        assert msg.content == "voice_media_123"

    # ---------- 消息解析：视频 / 短视频 ----------

    def test_parse_video_message(self) -> None:
        """解析视频消息。"""
        adapter = self._get_adapter()
        body = _build_video_xml("user1", "gh_official", "video")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "video"
        assert msg.content == "video_media_123"

    def test_parse_shortvideo_message(self) -> None:
        """解析短视频消息。"""
        adapter = self._get_adapter()
        body = _build_video_xml("user1", "gh_official", "shortvideo")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "shortvideo"
        assert msg.content == "video_media_123"

    # ---------- 消息解析：位置 ----------

    def test_parse_location_message(self) -> None:
        """解析位置消息。"""
        adapter = self._get_adapter()
        body = _build_location_xml("user1", "gh_official")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "location"
        assert "39.908860" in msg.content
        assert "天安门广场" in msg.content

    # ---------- 消息解析：链接 ----------

    def test_parse_link_message(self) -> None:
        """解析链接消息。"""
        adapter = self._get_adapter()
        body = _build_link_xml("user1", "gh_official")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "link"
        assert "CkyClaw 官网" in msg.content
        assert "https://ckyclaw.com" in msg.content

    # ---------- 消息解析：事件 ----------

    def test_parse_event_subscribe(self) -> None:
        """解析关注事件。"""
        adapter = self._get_adapter()
        body = _build_event_xml("user1", "gh_official", "subscribe")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "event"
        assert msg.content == "event:subscribe"
        assert msg.raw_data["_to_user"] == "gh_official"

    def test_parse_event_unsubscribe(self) -> None:
        """解析取消关注事件。"""
        adapter = self._get_adapter()
        body = _build_event_xml("user1", "gh_official", "unsubscribe")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.content == "event:unsubscribe"

    # ---------- 消息解析：异常 ----------

    def test_parse_invalid_xml(self) -> None:
        """无效 XML 返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not xml", _WECHAT_OFFICIAL_CONFIG) is None

    def test_parse_empty_body(self) -> None:
        """空消息体返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"", _WECHAT_OFFICIAL_CONFIG) is None

    # ---------- URL 验证 ----------

    def test_handle_verification(self) -> None:
        """URL 验证请求返回 echostr。"""
        adapter = self._get_adapter()
        result = adapter.handle_verification(
            b"", {"echostr": "echo_test_123"}, _WECHAT_OFFICIAL_CONFIG
        )
        assert result == "echo_test_123"

    def test_handle_verification_no_echostr(self) -> None:
        """非验证请求返回 None。"""
        adapter = self._get_adapter()
        result = adapter.handle_verification(b"", {}, _WECHAT_OFFICIAL_CONFIG)
        assert result is None

    # ---------- 被动回复 ----------

    def test_build_passive_reply(self) -> None:
        """构造被动回复 XML。"""
        from app.services.channel_adapters.wechat_official import build_passive_reply

        xml = build_passive_reply("hello user", "user_openid", "gh_official")
        assert "<ToUserName><![CDATA[user_openid]]>" in xml
        assert "<FromUserName><![CDATA[gh_official]]>" in xml
        assert "<Content><![CDATA[hello user]]>" in xml
        assert "<MsgType><![CDATA[text]]>" in xml
        assert "<CreateTime>" in xml

    # ---------- 客服消息推送 ----------

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """客服消息推送成功。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "test_access_token", "expires_in": 7200}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECHAT_OFFICIAL_CONFIG, "user_openid", "hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_credentials(self) -> None:
        """缺少 appid/appsecret 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_token_error(self) -> None:
        """获取 access_token 失败。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 40013, "errmsg": "invalid appid"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECHAT_OFFICIAL_CONFIG, "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """客服消息 API 返回错误。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok", "expires_in": 7200}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 45015, "errmsg": "out of response count limit"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECHAT_OFFICIAL_CONFIG, "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_network_error(self) -> None:
        """网络异常。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok", "expires_in": 7200}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_WECHAT_OFFICIAL_CONFIG, "user1", "hello")
        assert result is False

    # ---------- 模板消息 ----------

    @pytest.mark.asyncio
    async def test_send_template_message_success(self) -> None:
        """模板消息发送成功。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok", "expires_in": 7200}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 0, "errmsg": "ok", "msgid": 12345}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        template_data = {
            "first": {"value": "您好", "color": "#173177"},
            "keyword1": {"value": "Agent 运行完成"},
        }

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_template_message(
                _WECHAT_OFFICIAL_CONFIG, "user_openid", "tpl_1234", template_data, url="https://ckyclaw.com"
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_template_message_error(self) -> None:
        """模板消息发送失败。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok", "expires_in": 7200}

        mock_send_resp = MagicMock()
        mock_send_resp.json.return_value = {"errcode": 40037, "errmsg": "invalid template_id"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(return_value=mock_send_resp)

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_template_message(
                _WECHAT_OFFICIAL_CONFIG, "user1", "bad_tpl", {}
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_template_message_no_credentials(self) -> None:
        """缺少凭证时模板消息发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_template_message({}, "user1", "tpl_1234", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_template_message_network_error(self) -> None:
        """模板消息网络异常。"""
        adapter = self._get_adapter()

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok", "expires_in": 7200}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_token_resp)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_template_message(
                _WECHAT_OFFICIAL_CONFIG, "user1", "tpl_1234", {}
            )
        assert result is False

    # ---------- 注册表集成 ----------

    def test_adapter_in_registry(self) -> None:
        """适配器已注册在全局注册表中。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.wechat_official import WeChatOfficialAdapter

        adapter = get_adapter("wechat_official")
        assert isinstance(adapter, WeChatOfficialAdapter)

    # ---------- 加解密（安全模式） ----------

    def test_decrypt_encrypted_message(self) -> None:
        """解密安全模式下的加密消息。"""
        from app.services.channel_adapters.wechat_official import _decrypt_message

        appid = "wx_test_appid"
        encoding_aes_key = base64.b64encode(b"a" * 32).decode().rstrip("=")
        aes_key = base64.b64decode(encoding_aes_key + "=")
        iv = aes_key[:16]

        # 构造明文：random(16) + msg_len(4) + msg + appid
        import os as _os
        random_bytes = _os.urandom(16)
        msg = "<xml><Content>encrypted hello</Content></xml>"
        msg_bytes = msg.encode("utf-8")
        appid_bytes = appid.encode("utf-8")
        content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + appid_bytes

        # PKCS7 填充 + AES 加密
        padder = PKCS7(128).padder()
        padded = padder.update(content) + padder.finalize()
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        encrypt_text = base64.b64encode(encrypted).decode()

        result = _decrypt_message(encrypt_text, encoding_aes_key, appid)
        assert result == msg

    def test_decrypt_message_appid_mismatch(self) -> None:
        """AppID 不匹配时解密返回 None。"""
        from app.services.channel_adapters.wechat_official import _decrypt_message

        encoding_aes_key = base64.b64encode(b"a" * 32).decode().rstrip("=")
        aes_key = base64.b64decode(encoding_aes_key + "=")
        iv = aes_key[:16]

        import os as _os
        random_bytes = _os.urandom(16)
        msg = "<xml><Content>test</Content></xml>"
        msg_bytes = msg.encode("utf-8")
        wrong_appid = "wrong_appid".encode("utf-8")
        content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + wrong_appid

        padder = PKCS7(128).padder()
        padded = padder.update(content) + padder.finalize()
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        encrypt_text = base64.b64encode(encrypted).decode()

        result = _decrypt_message(encrypt_text, encoding_aes_key, "wx_test_appid")
        assert result is None

    def test_decrypt_message_empty_key(self) -> None:
        """空 encoding_aes_key 返回 None。"""
        from app.services.channel_adapters.wechat_official import _decrypt_message

        result = _decrypt_message("encrypted_data", "", "appid")
        assert result is None

    def test_decrypt_message_invalid_data(self) -> None:
        """无效密文数据返回 None。"""
        from app.services.channel_adapters.wechat_official import _decrypt_message

        encoding_aes_key = base64.b64encode(b"a" * 32).decode().rstrip("=")
        result = _decrypt_message("not_valid_base64!!!", encoding_aes_key, "appid")
        assert result is None

    def test_parse_encrypted_message(self) -> None:
        """解析安全模式加密消息（端到端）。"""
        adapter = self._get_adapter()

        appid = "wx_test_appid"
        encoding_aes_key = base64.b64encode(b"a" * 32).decode().rstrip("=")
        aes_key = base64.b64decode(encoding_aes_key + "=")
        iv = aes_key[:16]

        # 构造内层 XML
        inner_xml = (
            "<xml>"
            "<ToUserName><![CDATA[gh_official]]></ToUserName>"
            "<FromUserName><![CDATA[enc_user]]></FromUserName>"
            "<CreateTime>1609459200</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[encrypted hello]]></Content>"
            "<MsgId>999</MsgId>"
            "</xml>"
        )

        # 加密
        import os as _os
        random_bytes = _os.urandom(16)
        msg_bytes = inner_xml.encode("utf-8")
        appid_bytes = appid.encode("utf-8")
        content = random_bytes + struct.pack("!I", len(msg_bytes)) + msg_bytes + appid_bytes

        padder = PKCS7(128).padder()
        padded = padder.update(content) + padder.finalize()
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        encrypt_text = base64.b64encode(encrypted).decode()

        # 构造外层 XML（安全模式下微信发来的格式）
        outer_xml = (
            "<xml>"
            f"<Encrypt><![CDATA[{encrypt_text}]]></Encrypt>"
            "</xml>"
        ).encode("utf-8")

        config = {
            "appid": appid,
            "appsecret": "secret",
            "token": "tok",
            "encoding_aes_key": encoding_aes_key,
        }
        msg = adapter.parse_message(outer_xml, config)
        assert msg is not None
        assert msg.sender_id == "enc_user"
        assert msg.content == "encrypted hello"
        assert msg.message_type == "text"

    # ---------- _extract_content 未知类型 ----------

    def test_parse_unknown_message_type(self) -> None:
        """未知消息类型返回空内容。"""
        adapter = self._get_adapter()
        body = (
            "<xml>"
            "<ToUserName><![CDATA[gh_official]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1609459200</CreateTime>"
            "<MsgType><![CDATA[unknown_type]]></MsgType>"
            "</xml>"
        ).encode("utf-8")
        msg = adapter.parse_message(body, _WECHAT_OFFICIAL_CONFIG)
        assert msg is not None
        assert msg.message_type == "unknown_type"
        assert msg.content == ""

    # ---------- access_token 获取 ----------

    @pytest.mark.asyncio
    async def test_get_access_token_network_error(self) -> None:
        """access_token 获取网络异常。"""
        from app.services.channel_adapters.wechat_official import _get_access_token

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("network error"))

        with patch("app.services.channel_adapters.wechat_official.httpx.AsyncClient", return_value=mock_client):
            result = await _get_access_token("appid", "secret")
        assert result is None


# ========== Slack 适配器测试 ==========

_SLACK_CONFIG: dict[str, Any] = {
    "signing_secret": "slack_test_signing_secret",
    "bot_token": "xoxb-test-bot-token",
}


def _make_slack_signature(
    signing_secret: str, timestamp: str, body: str
) -> str:
    """按 Slack 规则生成请求签名。"""
    sig_basestring = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_slack_event(
    event_type: str = "message",
    user: str = "U12345",
    text: str = "hello",
    channel: str = "C67890",
    subtype: str | None = None,
    bot_id: str | None = None,
) -> dict[str, Any]:
    """构造 Slack event_callback 消息体。"""
    event: dict[str, Any] = {
        "type": event_type,
        "user": user,
        "text": text,
        "channel": channel,
        "ts": "1609459200.000100",
    }
    if subtype is not None:
        event["subtype"] = subtype
    if bot_id is not None:
        event["bot_id"] = bot_id
    return {
        "type": "event_callback",
        "event": event,
        "team_id": "T_TEAM",
        "event_id": "Ev_TEST",
    }


class TestSlackAdapter:
    """Slack 渠道适配器测试。"""

    def _get_adapter(self):
        from app.services.channel_adapters.slack import SlackAdapter
        return SlackAdapter()

    # ---------- 签名验证 ----------

    def test_verify_request_valid(self) -> None:
        """有效 HMAC-SHA256 签名验证通过。"""
        adapter = self._get_adapter()
        ts = str(int(time.time()))
        body_str = '{"type":"event_callback"}'
        sig = _make_slack_signature(_SLACK_CONFIG["signing_secret"], ts, body_str)
        headers = {
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": ts,
        }
        assert adapter.verify_request(headers, body_str.encode(), _SLACK_CONFIG) is True

    def test_verify_request_invalid_signature(self) -> None:
        """无效签名验证失败。"""
        adapter = self._get_adapter()
        ts = str(int(time.time()))
        headers = {
            "X-Slack-Signature": "v0=invalid_signature",
            "X-Slack-Request-Timestamp": ts,
        }
        assert adapter.verify_request(headers, b'{}', _SLACK_CONFIG) is False

    def test_verify_request_missing_headers(self) -> None:
        """缺少签名 headers 验证失败。"""
        adapter = self._get_adapter()
        # 缺少 X-Slack-Signature
        assert adapter.verify_request(
            {"X-Slack-Request-Timestamp": "123"}, b'{}', _SLACK_CONFIG
        ) is False
        # 缺少 X-Slack-Request-Timestamp
        assert adapter.verify_request(
            {"X-Slack-Signature": "v0=abc"}, b'{}', _SLACK_CONFIG
        ) is False

    def test_verify_request_no_signing_secret(self) -> None:
        """未配置 signing_secret 验证失败。"""
        adapter = self._get_adapter()
        assert adapter.verify_request({}, b'{}', {}) is False

    def test_verify_request_timestamp_replay(self) -> None:
        """时间戳超出容差（防重放攻击）。"""
        adapter = self._get_adapter()
        old_ts = str(int(time.time()) - 600)  # 10 分钟前
        body_str = '{"type":"event_callback"}'
        sig = _make_slack_signature(_SLACK_CONFIG["signing_secret"], old_ts, body_str)
        headers = {
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": old_ts,
        }
        assert adapter.verify_request(headers, body_str.encode(), _SLACK_CONFIG) is False

    def test_verify_request_custom_tolerance(self) -> None:
        """自定义时间戳容差。"""
        adapter = self._get_adapter()
        old_ts = str(int(time.time()) - 400)  # 超过 300 秒但在 600 秒内
        body_str = '{"data":true}'
        sig = _make_slack_signature(_SLACK_CONFIG["signing_secret"], old_ts, body_str)
        config = {**_SLACK_CONFIG, "timestamp_tolerance": 600}
        headers = {
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": old_ts,
        }
        assert adapter.verify_request(headers, body_str.encode(), config) is True

    def test_verify_request_invalid_timestamp(self) -> None:
        """无效时间戳格式。"""
        adapter = self._get_adapter()
        headers = {
            "X-Slack-Signature": "v0=abc",
            "X-Slack-Request-Timestamp": "not_a_number",
        }
        assert adapter.verify_request(headers, b'{}', _SLACK_CONFIG) is False

    def test_verify_request_lowercase_headers(self) -> None:
        """小写 header 名兼容。"""
        adapter = self._get_adapter()
        ts = str(int(time.time()))
        body_str = '{"test":1}'
        sig = _make_slack_signature(_SLACK_CONFIG["signing_secret"], ts, body_str)
        headers = {
            "x-slack-signature": sig,
            "x-slack-request-timestamp": ts,
        }
        assert adapter.verify_request(headers, body_str.encode(), _SLACK_CONFIG) is True

    # ---------- 消息解析 ----------

    def test_parse_text_message(self) -> None:
        """解析文本消息。"""
        adapter = self._get_adapter()
        event_data = _build_slack_event(text="hello world")
        body = json.dumps(event_data).encode()
        msg = adapter.parse_message(body, _SLACK_CONFIG)
        assert msg is not None
        assert msg.sender_id == "U12345"
        assert msg.content == "hello world"
        assert msg.message_type == "text"
        assert msg.raw_data["_channel"] == "C67890"

    def test_parse_ignore_bot_message(self) -> None:
        """忽略 bot 消息，避免消息循环。"""
        adapter = self._get_adapter()
        event_data = _build_slack_event(bot_id="B_BOT")
        body = json.dumps(event_data).encode()
        msg = adapter.parse_message(body, _SLACK_CONFIG)
        assert msg is None

    def test_parse_ignore_system_subtype(self) -> None:
        """忽略系统子类型消息。"""
        adapter = self._get_adapter()
        for subtype in ["bot_message", "channel_join", "channel_leave"]:
            event_data = _build_slack_event(subtype=subtype)
            body = json.dumps(event_data).encode()
            msg = adapter.parse_message(body, _SLACK_CONFIG)
            assert msg is None, f"subtype '{subtype}' should be ignored"

    def test_parse_non_event_callback(self) -> None:
        """非 event_callback 类型返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"type": "url_verification", "challenge": "abc"}).encode()
        msg = adapter.parse_message(body, _SLACK_CONFIG)
        assert msg is None

    def test_parse_non_message_event(self) -> None:
        """非 message 事件作为 event 类型返回。"""
        adapter = self._get_adapter()
        event_data = {
            "type": "event_callback",
            "event": {"type": "app_mention", "user": "U999", "text": "<@B123> help"},
        }
        body = json.dumps(event_data).encode()
        msg = adapter.parse_message(body, _SLACK_CONFIG)
        assert msg is not None
        assert msg.message_type == "event"
        assert msg.content == "event:app_mention"

    def test_parse_no_user(self) -> None:
        """缺少 user 的消息返回 None。"""
        adapter = self._get_adapter()
        event_data = {
            "type": "event_callback",
            "event": {"type": "message", "text": "orphan"},
        }
        body = json.dumps(event_data).encode()
        msg = adapter.parse_message(body, _SLACK_CONFIG)
        assert msg is None

    def test_parse_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = self._get_adapter()
        assert adapter.parse_message(b"not json!", _SLACK_CONFIG) is None

    # ---------- URL 验证 ----------

    def test_handle_verification(self) -> None:
        """URL 验证请求返回 challenge。"""
        adapter = self._get_adapter()
        body = json.dumps({
            "type": "url_verification",
            "challenge": "challenge_abc_123",
            "token": "deprecated_token",
        }).encode()
        result = adapter.handle_verification(body, {}, _SLACK_CONFIG)
        assert result == "challenge_abc_123"

    def test_handle_verification_not_verification(self) -> None:
        """非验证请求返回 None。"""
        adapter = self._get_adapter()
        body = json.dumps({"type": "event_callback"}).encode()
        result = adapter.handle_verification(body, {}, _SLACK_CONFIG)
        assert result is None

    def test_handle_verification_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        adapter = self._get_adapter()
        result = adapter.handle_verification(b"bad json", {}, _SLACK_CONFIG)
        assert result is None

    # ---------- 消息推送 ----------

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """Slack 消息发送成功。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "channel": "C67890", "ts": "123456"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.slack.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_SLACK_CONFIG, "C67890", "hello slack")
        assert result is True
        # 验证 Authorization header
        call_args = mock_client.post.call_args
        headers = call_args[1].get("headers", {})
        assert headers["Authorization"] == "Bearer xoxb-test-bot-token"

    @pytest.mark.asyncio
    async def test_send_message_no_token(self) -> None:
        """缺少 bot_token 发送失败。"""
        adapter = self._get_adapter()
        result = await adapter.send_message({}, "C67890", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_api_error(self) -> None:
        """Slack API 返回错误。"""
        adapter = self._get_adapter()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "error": "channel_not_found"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("app.services.channel_adapters.slack.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_SLACK_CONFIG, "C_BAD", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_network_error(self) -> None:
        """网络异常。"""
        adapter = self._get_adapter()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch("app.services.channel_adapters.slack.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_message(_SLACK_CONFIG, "C67890", "hello")
        assert result is False

    # ---------- 注册表集成 ----------

    def test_adapter_in_registry(self) -> None:
        """适配器已注册在全局注册表中。"""
        from app.services.channel_adapters import get_adapter
        from app.services.channel_adapters.slack import SlackAdapter

        adapter = get_adapter("slack")
        assert isinstance(adapter, SlackAdapter)
