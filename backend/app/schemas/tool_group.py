"""Tool Group 请求/响应模型。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

_TOOL_GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,127}$")

_VALID_SCHEMA_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


class ToolDefinition(BaseModel):
    """工具组内单个工具的元数据定义。"""

    name: str = Field(..., min_length=1, max_length=128, description="工具名称，仅允许小写字母、数字和下划线")
    description: str = Field(default="", description="工具功能描述，LLM 据此决定是否调用该工具")
    parameters_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="符合 JSON Schema Draft 7 的参数定义",
    )

    @field_validator("name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """校验工具名称格式：小写字母开头，仅含小写字母/数字/下划线。"""
        if not _TOOL_NAME_PATTERN.match(v):
            raise ValueError(
                f"工具名称 '{v}' 格式无效。要求：以小写字母开头，仅包含小写字母、数字和下划线，长度 1-128"
            )
        return v

    @field_validator("parameters_schema")
    @classmethod
    def validate_parameters_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """校验 parameters_schema 基本结构符合 JSON Schema 规范。"""
        if not v:
            return {"type": "object", "properties": {}}
        schema_type = v.get("type")
        if schema_type and schema_type not in _VALID_SCHEMA_TYPES:
            raise ValueError(
                f"parameters_schema.type '{schema_type}' 无效。"
                f"支持的类型: {', '.join(sorted(_VALID_SCHEMA_TYPES))}"
            )
        if schema_type == "object":
            props = v.get("properties")
            if props is not None and not isinstance(props, dict):
                raise ValueError("parameters_schema.properties 必须是对象")
            required = v.get("required")
            if required is not None:
                if not isinstance(required, list):
                    raise ValueError("parameters_schema.required 必须是数组")
                if props:
                    unknown = set(required) - set(props.keys())
                    if unknown:
                        raise ValueError(
                            f"required 中包含未在 properties 中定义的参数: {', '.join(sorted(unknown))}"
                        )
        return v


class ToolGroupCreate(BaseModel):
    """创建工具组请求体。"""

    name: str = Field(..., min_length=3, max_length=64, description="工具组唯一标识")
    description: str = Field(default="", description="工具组描述")
    tools: list[ToolDefinition] = Field(default_factory=list, description="工具定义列表")
    conditions: dict[str, Any] = Field(default_factory=dict, description="条件启用配置")

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
    conditions: dict[str, Any] | None = None
    is_enabled: bool | None = None


class ToolGroupResponse(BaseModel):
    """工具组详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    tools: list[dict[str, Any]]
    conditions: dict[str, Any]
    source: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ToolGroupListResponse(BaseModel):
    """工具组列表响应。"""

    data: list[ToolGroupResponse]
    total: int
