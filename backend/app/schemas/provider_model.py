"""Provider Model 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderModelCreate(BaseModel):
    """创建 Provider Model 请求体。"""

    model_name: str = Field(..., min_length=1, max_length=128, description="模型标识（如 gpt-4o）")
    display_name: str = Field(default="", max_length=128, description="显示名称")
    context_window: int = Field(default=4096, ge=1, description="上下文窗口大小")
    max_output_tokens: int | None = Field(default=None, ge=1, description="最大输出 Token 数")
    prompt_price_per_1k: float = Field(default=0.0, ge=0, description="输入价格/千 Token")
    completion_price_per_1k: float = Field(default=0.0, ge=0, description="输出价格/千 Token")
    is_enabled: bool = Field(default=True, description="是否启用")


class ProviderModelUpdate(BaseModel):
    """更新 Provider Model 请求体。"""

    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    prompt_price_per_1k: float | None = Field(default=None, ge=0)
    completion_price_per_1k: float | None = Field(default=None, ge=0)
    is_enabled: bool | None = None


class ProviderModelResponse(BaseModel):
    """Provider Model 详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    model_name: str
    display_name: str
    context_window: int
    max_output_tokens: int | None
    prompt_price_per_1k: float
    completion_price_per_1k: float
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ProviderModelListResponse(BaseModel):
    """Provider Model 列表响应。"""

    data: list[ProviderModelResponse]
    total: int
