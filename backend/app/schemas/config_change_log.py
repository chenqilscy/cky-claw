"""配置变更日志 Schema。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_CHANGE_SOURCES = {"web_ui", "api", "system", "rollback"}
VALID_ENTITY_TYPES = {"agent", "guardrail", "provider", "tool-group", "session", "team", "workflow", "mcp-server"}


class ConfigChangeLogCreate(BaseModel):
    """创建配置变更日志。"""

    config_key: str = Field(..., max_length=255)
    entity_type: str = Field(..., max_length=64)
    entity_id: str = Field(..., max_length=255)
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    change_source: str = Field(default="api")
    description: str = Field(default="")

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(f"不支持的实体类型: {v}，可选: {VALID_ENTITY_TYPES}")
        return v

    @field_validator("change_source")
    @classmethod
    def validate_change_source(cls, v: str) -> str:
        if v not in VALID_CHANGE_SOURCES:
            raise ValueError(f"不支持的变更来源: {v}，可选: {VALID_CHANGE_SOURCES}")
        return v


class ConfigChangeLogResponse(BaseModel):
    """配置变更日志响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    config_key: str
    entity_type: str
    entity_id: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    changed_by: uuid.UUID | None
    change_source: str
    rollback_ref: uuid.UUID | None
    description: str
    org_id: uuid.UUID | None
    created_at: datetime


class ConfigChangeLogListResponse(BaseModel):
    """配置变更日志列表响应。"""

    data: list[ConfigChangeLogResponse]
    total: int


class RollbackPreviewResponse(BaseModel):
    """回滚预览响应。

    注意：current_value 为该变更记录时的新值，非实时当前值。
    若配置已被后续操作修改，实际当前值可能与此不同。
    """

    change_id: uuid.UUID
    config_key: str
    entity_type: str
    entity_id: str
    current_value: dict[str, Any] | None = Field(description="变更时的值，非实时当前值")
    rollback_to_value: dict[str, Any] | None
