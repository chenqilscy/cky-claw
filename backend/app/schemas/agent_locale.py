"""Agent 多语言 Instructions 请求/响应模型。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

# BCP 47 简化校验：语言[-脚本][-地区]，如 zh-CN、en-US、ja-JP、pt-BR
_BCP47_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{4})?(-[A-Z]{2}|\d{3})?$")


class AgentLocaleCreate(BaseModel):
    """新增 Agent 语言版本请求体。"""

    locale: str = Field(..., min_length=2, max_length=16, description="BCP 47 语言标识")
    instructions: str = Field(..., description="该语言版本的 Instructions 全文")
    is_default: bool = Field(default=False, description="是否设为默认语言版本")

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        """校验 locale 格式。"""
        if not _BCP47_PATTERN.match(v):
            raise ValueError(f"locale 格式无效，应为 BCP 47 格式（如 zh-CN、en-US），收到: {v}")
        return v


class AgentLocaleUpdate(BaseModel):
    """更新 Agent 语言版本请求体。"""

    instructions: str = Field(..., description="更新后的 Instructions 全文")
    is_default: bool | None = Field(default=None, description="是否设为默认")


class AgentLocaleResponse(BaseModel):
    """Agent 语言版本响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    locale: str
    instructions: str
    is_default: bool
    updated_at: datetime


class AgentLocaleListResponse(BaseModel):
    """Agent 语言版本列表响应。"""

    data: list[AgentLocaleResponse]
