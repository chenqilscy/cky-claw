"""渠道适配器抽象基类与标准消息模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """渠道消息标准化模型 — 将各平台消息格式统一为通用结构。"""

    sender_id: str
    content: str
    message_type: str = "text"  # text / image / file / event
    raw_data: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(ABC):
    """IM 渠道适配器抽象基类。

    每个 IM 平台（企业微信、钉钉等）实现一个子类，封装：
    - 请求签名验证
    - 消息解析（平台格式 → ChannelMessage）
    - URL 验证回调
    - 消息推送（ChannelMessage → 平台 API）
    """

    @abstractmethod
    def verify_request(
        self, headers: dict[str, str], body: bytes, app_config: dict[str, Any]
    ) -> bool:
        """验证请求签名/来源。

        Args:
            headers: HTTP 请求头。
            body: 原始请求体。
            app_config: IMChannel.app_config 存储的平台配置。

        Returns:
            签名验证是否通过。
        """

    @abstractmethod
    def parse_message(
        self, body: bytes, app_config: dict[str, Any]
    ) -> ChannelMessage | None:
        """从平台特定格式解析出通用消息。

        Returns:
            解析后的 ChannelMessage，None 表示忽略此请求（如事件确认/验证请求）。
        """

    @abstractmethod
    def handle_verification(
        self, body: bytes, query_params: dict[str, str], app_config: dict[str, Any]
    ) -> str | None:
        """处理平台的 URL 验证请求。

        Returns:
            验证响应内容（直接返回给平台），None 表示此请求不是验证请求。
        """

    @abstractmethod
    async def send_message(
        self, app_config: dict[str, Any], recipient_id: str, content: str
    ) -> bool:
        """向平台用户发送消息。

        Args:
            app_config: IMChannel.app_config 存储的平台配置。
            recipient_id: 接收方标识（用户 ID / 会话 ID）。
            content: 消息文本内容。

        Returns:
            发送是否成功。
        """
