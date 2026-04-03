"""MCP Server 配置请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_TRANSPORT_TYPES = {"stdio", "sse", "http"}

# auth_config 中需要脱敏的字段名
_SENSITIVE_AUTH_FIELDS = {"api_key", "secret", "token", "password", "client_secret", "refresh_token"}


def _mask_auth_config(auth: dict | None) -> dict | None:
    """对 auth_config 中的敏感字段进行脱敏。"""
    if not auth:
        return auth
    masked = {}
    for key, value in auth.items():
        if key.lower() in _SENSITIVE_AUTH_FIELDS and isinstance(value, str) and len(value) > 0:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


class MCPServerCreate(BaseModel):
    """创建 MCP Server 配置。"""

    name: str = Field(..., min_length=2, max_length=64, description="MCP Server 唯一标识")
    description: str = Field(default="", description="描述")
    transport_type: str = Field(..., description="传输类型：stdio / sse / http")
    command: str | None = Field(default=None, description="stdio 模式命令")
    url: str | None = Field(default=None, description="sse/http 模式 URL")
    env: dict = Field(default_factory=dict, description="环境变量")
    auth_config: dict | None = Field(default=None, description="认证配置")
    is_enabled: bool = Field(default=True, description="是否启用")

    @field_validator("transport_type")
    @classmethod
    def validate_transport_type(cls, v: str) -> str:
        if v not in VALID_TRANSPORT_TYPES:
            raise ValueError(f"transport_type 必须是 {VALID_TRANSPORT_TYPES} 之一")
        return v

    @model_validator(mode="after")
    def validate_transport_fields(self) -> MCPServerCreate:
        if self.transport_type == "stdio" and not self.command:
            raise ValueError("stdio 模式必须提供 command")
        if self.transport_type in ("sse", "http") and not self.url:
            raise ValueError(f"{self.transport_type} 模式必须提供 url")
        return self


class MCPServerUpdate(BaseModel):
    """更新 MCP Server 配置（PATCH 语义）。"""

    description: str | None = None
    transport_type: str | None = None
    command: str | None = None
    url: str | None = None
    env: dict | None = None
    auth_config: dict | None = None
    is_enabled: bool | None = None

    @field_validator("transport_type")
    @classmethod
    def validate_transport_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_TRANSPORT_TYPES:
            raise ValueError(f"transport_type 必须是 {VALID_TRANSPORT_TYPES} 之一")
        return v


class MCPServerResponse(BaseModel):
    """MCP Server 配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    transport_type: str
    command: str | None
    url: str | None
    env: dict
    auth_config: dict | None
    is_enabled: bool
    org_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @field_validator("auth_config", mode="before")
    @classmethod
    def mask_auth(cls, v: dict | None) -> dict | None:
        return _mask_auth_config(v)


class MCPServerListResponse(BaseModel):
    """MCP Server 列表响应。"""

    items: list[MCPServerResponse]
    total: int
