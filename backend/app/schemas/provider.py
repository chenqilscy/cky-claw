"""Model Provider 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VALID_PROVIDER_TYPES = {
    "openai", "anthropic", "azure", "deepseek", "qwen",
    "doubao", "zhipu", "moonshot", "custom",
}

_VALID_AUTH_TYPES = {"api_key", "azure_ad", "custom_header"}


class ProviderCreate(BaseModel):
    """创建 Provider 请求体。"""

    name: str = Field(..., min_length=1, max_length=64, description="厂商显示名称")
    provider_type: str = Field(..., description="厂商类型")
    base_url: str = Field(..., min_length=1, max_length=512, description="API 端点 URL")
    api_key: str = Field(..., min_length=1, description="API Key（明文，服务端加密存储）")
    auth_type: str = Field(default="api_key", description="认证类型")
    auth_config: dict = Field(default_factory=dict, description="额外认证参数")
    rate_limit_rpm: int | None = Field(default=None, ge=0, description="每分钟请求数上限")
    rate_limit_tpm: int | None = Field(default=None, ge=0, description="每分钟 Token 数上限")

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str) -> str:
        if v not in _VALID_PROVIDER_TYPES:
            raise ValueError(f"provider_type 必须是 {_VALID_PROVIDER_TYPES} 之一")
        return v

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, v: str) -> str:
        if v not in _VALID_AUTH_TYPES:
            raise ValueError(f"auth_type 必须是 {_VALID_AUTH_TYPES} 之一")
        return v


class ProviderUpdate(BaseModel):
    """更新 Provider 请求体（PATCH 语义，所有字段可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    provider_type: str | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, description="新 API Key（可选更新）")
    auth_type: str | None = None
    auth_config: dict | None = None
    rate_limit_rpm: int | None = Field(default=None, ge=0)
    rate_limit_tpm: int | None = Field(default=None, ge=0)

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PROVIDER_TYPES:
            raise ValueError(f"provider_type 必须是 {_VALID_PROVIDER_TYPES} 之一")
        return v

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_AUTH_TYPES:
            raise ValueError(f"auth_type 必须是 {_VALID_AUTH_TYPES} 之一")
        return v


class ProviderToggle(BaseModel):
    """启用/禁用请求体。"""

    is_enabled: bool


class ProviderResponse(BaseModel):
    """Provider 详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    api_key_set: bool = Field(description="是否已设置 API Key（不返回密钥本身）")
    auth_type: str
    auth_config: dict
    rate_limit_rpm: int | None
    rate_limit_tpm: int | None
    is_enabled: bool
    org_id: uuid.UUID | None
    last_health_check: datetime | None
    health_status: str
    created_at: datetime
    updated_at: datetime


class ProviderListResponse(BaseModel):
    """Provider 列表响应。"""

    data: list[ProviderResponse]
    total: int
    limit: int
    offset: int


class ProviderTestResult(BaseModel):
    """Provider 连通性测试结果。"""

    success: bool
    latency_ms: int = 0
    error: str | None = None
    model_used: str | None = None
