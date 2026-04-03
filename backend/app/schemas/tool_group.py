"""Tool Group 请求/响应模型。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_TOOL_GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


class ToolDefinition(BaseModel):
    """工具组内单个工具的元数据定义。"""

    name: str = Field(..., min_length=1, max_length=128, description="工具名称")
    description: str = Field(default="", description="工具描述")
    parameters_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema 参数定义",
    )


class ToolGroupCreate(BaseModel):
    """创建工具组请求体。"""

    name: str = Field(..., min_length=3, max_length=64, description="工具组唯一标识")
    description: str = Field(default="", description="工具组描述")
    tools: list[ToolDefinition] = Field(default_factory=list, description="工具定义列表")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _TOOL_GROUP_NAME_PATTERN.match(v):
            raise ValueError("名称只能包含小写字母、数字和连字符，且以字母或数字开头结尾，长度 3-64")
        return v


class ToolGroupUpdate(BaseModel):
    """更新工具组请求体（PATCH 语义，所有字段可选）。"""

    description: str | None = None
    tools: list[ToolDefinition] | None = None
    is_enabled: bool | None = None


class ToolGroupResponse(BaseModel):
    """工具组详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    tools: list[dict[str, Any]]
    source: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ToolGroupListResponse(BaseModel):
    """工具组列表响应。"""

    data: list[ToolGroupResponse]
    total: int
