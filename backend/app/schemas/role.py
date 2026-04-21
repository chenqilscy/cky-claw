"""角色 Schema。"""

from __future__ import annotations
import uuid
from datetime import datetime

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,62}[a-z0-9]$")

# 有效的资源类型
VALID_RESOURCES = {
    "agents", "providers", "workflows", "teams", "guardrails",
    "mcp_servers", "tool_groups", "skills", "templates", "memories",
    "runs", "traces", "approvals", "sessions", "token_usage",
    "audit_logs", "roles", "users",
}

# 有效的操作
VALID_ACTIONS = {"read", "write", "delete", "execute"}

class RoleCreate(BaseModel):
    """创建角色请求。"""

    name: str = Field(..., min_length=3, max_length=64, description="角色名称")
    description: str = Field("", max_length=256, description="角色描述")
    permissions: dict[str, list[str]] = Field(default_factory=dict, description="权限 {resource: [action]}")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError("角色名只能包含小写字母、数字、下划线和连字符，以小写字母开头")
        return v

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        for resource, actions in v.items():
            if resource not in VALID_RESOURCES:
                raise ValueError(f"无效的资源类型: {resource}")
            for action in actions:
                if action not in VALID_ACTIONS:
                    raise ValueError(f"无效的操作: {action}")
        return v

class RoleUpdate(BaseModel):
    """更新角色请求。"""

    description: str | None = Field(None, max_length=256)
    permissions: dict[str, list[str]] | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: dict[str, list[str]] | None) -> dict[str, list[str]] | None:
        if v is None:
            return v
        for resource, actions in v.items():
            if resource not in VALID_RESOURCES:
                raise ValueError(f"无效的资源类型: {resource}")
            for action in actions:
                if action not in VALID_ACTIONS:
                    raise ValueError(f"无效的操作: {action}")
        return v

class RoleResponse(BaseModel):
    """角色响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    permissions: dict[str, list[str]]
    is_system: bool
    created_at: datetime
    updated_at: datetime

class RoleListResponse(BaseModel):
    """角色列表响应。"""

    data: list[RoleResponse]
    total: int
    limit: int = 20
    offset: int = 0

class UserRoleAssign(BaseModel):
    """分配角色请求。"""

    role_id: uuid.UUID = Field(..., description="角色 ID")
