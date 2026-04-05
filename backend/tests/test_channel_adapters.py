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
        assert get_adapter("slack") is None

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
