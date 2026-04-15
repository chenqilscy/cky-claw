"""IM 渠道配置请求/响应模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

VALID_CHANNEL_TYPES = {"wecom", "dingtalk", "slack", "telegram", "feishu", "webhook", "discord", "wechat_official"}

_SENSITIVE_CONFIG_FIELDS = {"token", "secret", "api_key", "app_secret", "client_secret", "password"}


def _mask_app_config(config: dict[str, Any]) -> dict[str, Any]:
    """对 app_config 中的敏感字段进行脱敏。"""
    masked = {}
    for key, value in config.items():
        if key.lower() in _SENSITIVE_CONFIG_FIELDS and isinstance(value, str) and len(value) > 0:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


class IMChannelCreate(BaseModel):
    """创建 IM 渠道。"""

    name: str = Field(..., min_length=2, max_length=64, description="渠道唯一标识")
    description: str = Field(default="", description="描述")
    channel_type: str = Field(..., description="渠道类型：wecom/dingtalk/slack/telegram/feishu/webhook")
    webhook_url: str | None = Field(default=None, description="Webhook 回调 URL")
    webhook_secret: str | None = Field(default=None, description="Webhook 签名密钥")
    app_config: dict[str, Any] = Field(default_factory=dict, description="渠道应用配置（app_id、token 等）")
    agent_id: uuid.UUID | None = Field(default=None, description="绑定的 Agent ID")
    is_enabled: bool = Field(default=True, description="是否启用")
    notify_approvals: bool = Field(default=False, description="是否接收审批通知")
    approval_recipient_id: str | None = Field(default=None, max_length=128, description="审批通知接收方 ID")

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        if v not in VALID_CHANNEL_TYPES:
            raise ValueError(f"channel_type 必须是 {VALID_CHANNEL_TYPES} 之一")
        return v


class IMChannelUpdate(BaseModel):
    """更新 IM 渠道（PATCH 语义）。"""

    description: str | None = None
    channel_type: str | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None
    app_config: dict[str, Any] | None = None
    agent_id: uuid.UUID | None = None
    is_enabled: bool | None = None
    notify_approvals: bool | None = None
    approval_recipient_id: str | None = None

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CHANNEL_TYPES:
            raise ValueError(f"channel_type 必须是 {VALID_CHANNEL_TYPES} 之一")
        return v


class IMChannelResponse(BaseModel):
    """IM 渠道响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    channel_type: str
    webhook_url: str | None
    webhook_secret: str | None = None
    app_config: dict[str, Any]
    agent_id: uuid.UUID | None
    is_enabled: bool
    notify_approvals: bool
    approval_recipient_id: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("webhook_secret", mode="before")
    @classmethod
    def mask_secret(cls, v: str | None) -> str | None:
        if v and len(v) > 0:
            return "***"
        return v

    @field_validator("app_config", mode="before")
    @classmethod
    def mask_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _mask_app_config(v) if v else v


class IMChannelListResponse(BaseModel):
    """IM 渠道列表响应。"""

    data: list[IMChannelResponse]
    total: int
    limit: int = 20
    offset: int = 0


class IMWebhookPayload(BaseModel):
    """IM 渠道 Webhook 入站消息。"""

    channel_type: str
    sender_id: str = ""
    sender_name: str = ""
    content: str = ""
    message_id: str = ""
    conversation_id: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)
