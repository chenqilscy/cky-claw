"""Guardrail 规则请求/响应 Schema。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuardrailRuleCreate(BaseModel):
    """创建 Guardrail 规则请求。"""

    name: str = Field(..., min_length=2, max_length=64, description="规则唯一标识")
    description: str = Field(default="", description="规则描述")
    type: str = Field(default="input", description="护栏类型: input / output / tool")
    mode: str = Field(default="regex", description="检测模式: regex / keyword / llm")
    config: dict[str, Any] = Field(default_factory=dict, description="模式配置")
    conditions: dict[str, Any] = Field(default_factory=dict, description="条件启用配置")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"input", "output", "tool"}
        if v not in allowed:
            raise ValueError(f"type 必须是 {allowed} 之一")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = {"regex", "keyword", "llm"}
        if v not in allowed:
            raise ValueError(f"mode 必须是 {allowed} 之一")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$", v):
            raise ValueError("名称只能包含小写字母、数字、下划线和连字符")
        return v


class GuardrailRuleUpdate(BaseModel):
    """更新 Guardrail 规则请求（PATCH 语义）。"""

    description: str | None = None
    type: str | None = None
    mode: str | None = None
    config: dict[str, Any] | None = None
    conditions: dict[str, Any] | None = None
    is_enabled: bool | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"input", "output", "tool"}
            if v not in allowed:
                raise ValueError(f"type 必须是 {allowed} 之一")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"regex", "keyword", "llm"}
            if v not in allowed:
                raise ValueError(f"mode 必须是 {allowed} 之一")
        return v


class GuardrailRuleResponse(BaseModel):
    """Guardrail 规则响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    type: str
    mode: str
    config: dict[str, Any]
    conditions: dict[str, Any]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class GuardrailRuleListResponse(BaseModel):
    """Guardrail 规则列表响应。"""

    data: list[GuardrailRuleResponse]
    total: int
    limit: int = 20
    offset: int = 0
