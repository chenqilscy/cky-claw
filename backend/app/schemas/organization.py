"""Organization 请求/响应 Schema。"""

from __future__ import annotations
import uuid
from datetime import datetime

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")

class OrganizationCreate(BaseModel):
    """创建组织。"""

    name: str = Field(..., min_length=2, max_length=128, description="组织名称")
    slug: str = Field(..., min_length=3, max_length=64, description="唯一标识 (URL 友好)")
    description: str = Field(default="", description="描述")
    settings: dict[str, Any] = Field(default_factory=dict, description="组织设置")
    quota: dict[str, Any] = Field(default_factory=dict, description="配额限制")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_PATTERN.match(v):
            raise ValueError("slug 仅支持小写字母、数字和连字符，首尾必须是字母或数字，长度 3-64")
        return v

class OrganizationUpdate(BaseModel):
    """更新组织（PATCH）。"""

    name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None
    quota: dict[str, Any] | None = None
    is_active: bool | None = None

class OrganizationResponse(BaseModel):
    """组织响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str
    settings: dict[str, Any]
    quota: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class OrganizationListResponse(BaseModel):
    """组织列表响应。"""

    data: list[OrganizationResponse]
    total: int
    limit: int = 20
    offset: int = 0
