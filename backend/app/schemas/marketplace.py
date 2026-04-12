"""Marketplace 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceTemplateResponse(BaseModel):
    """市场模板展示响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    published: bool
    downloads: int
    rating: float
    rating_count: int
    author_org_id: uuid.UUID | None = None
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class MarketplaceListResponse(BaseModel):
    """市场模板列表响应。"""

    data: list[MarketplaceTemplateResponse]
    total: int
    limit: int
    offset: int


class PublishTemplateRequest(BaseModel):
    """发布模板到市场。"""

    template_id: uuid.UUID = Field(..., description="要发布的模板 ID")


class InstallTemplateRequest(BaseModel):
    """从市场安装模板。"""

    agent_name: str = Field(..., min_length=3, max_length=64, description="创建的 Agent 名称")
    overrides: dict[str, object] = Field(default_factory=dict, description="覆盖参数")


class ReviewCreate(BaseModel):
    """提交评价。"""

    score: int = Field(..., ge=1, le=5, description="评分（1-5 星）")
    comment: str = Field("", max_length=2000, description="评论")


class ReviewResponse(BaseModel):
    """评价响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: uuid.UUID
    user_id: uuid.UUID
    score: int
    comment: str
    created_at: datetime


class ReviewListResponse(BaseModel):
    """评价列表响应。"""

    data: list[ReviewResponse]
    total: int
