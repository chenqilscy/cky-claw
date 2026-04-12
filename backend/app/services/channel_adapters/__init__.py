"""IM 渠道适配器层 — 为每个 IM 平台提供消息格式转换、签名验证、消息推送能力。"""

from __future__ import annotations

from .base import ChannelAdapter, ChannelMessage
from .custom_webhook import CustomWebhookAdapter
from .dingtalk import DingTalkAdapter
from .discord import DiscordAdapter
from .feishu import FeishuAdapter
from .slack import SlackAdapter
from .telegram import TelegramAdapter
from .wechat_official import WeChatOfficialAdapter
from .wecom import WeComAdapter

# 适配器注册表：channel_type → Adapter 实例
_ADAPTER_REGISTRY: dict[str, ChannelAdapter] = {
    "wecom": WeComAdapter(),
    "dingtalk": DingTalkAdapter(),
    "feishu": FeishuAdapter(),
    "custom_webhook": CustomWebhookAdapter(),
    "wechat_official": WeChatOfficialAdapter(),
    "slack": SlackAdapter(),
    "telegram": TelegramAdapter(),
    "discord": DiscordAdapter(),
}


def get_adapter(channel_type: str) -> ChannelAdapter | None:
    """按渠道类型获取适配器实例。不支持的类型返回 None。"""
    return _ADAPTER_REGISTRY.get(channel_type)


__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "CustomWebhookAdapter",
    "DingTalkAdapter",
    "DiscordAdapter",
    "FeishuAdapter",
    "SlackAdapter",
    "TelegramAdapter",
    "WeChatOfficialAdapter",
    "WeComAdapter",
    "get_adapter",
]
