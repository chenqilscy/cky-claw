"""多环境管理 Schema。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class EnvironmentCreate(BaseModel):
    """创建环境请求。"""

    name: str = Field(..., min_length=2, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="")
    color: str = Field(default="#1890ff", min_length=4, max_length=16)
    sort_order: int = Field(default=0)
    is_protected: bool = Field(default=False)
    settings_override: dict[str, Any] = Field(default_factory=dict)


class EnvironmentUpdate(BaseModel):
    """更新环境请求。"""

    display_name: str | None = None
    description: str | None = None
    color: str | None = None
    sort_order: int | None = None
    is_protected: bool | None = None
    settings_override: dict[str, Any] | None = None


class EnvironmentResponse(BaseModel):
    """环境响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str
    color: str
    sort_order: int
    is_protected: bool
    settings_override: dict[str, Any]
    org_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class EnvironmentListResponse(BaseModel):
    """环境列表响应。"""

    data: list[EnvironmentResponse]
    total: int


class PublishRequest(BaseModel):
    """发布请求。"""

    version_id: uuid.UUID | None = None
    notes: str = Field(default="")


class RollbackRequest(BaseModel):
    """回滚请求。"""

    target_version_id: uuid.UUID | None = None
    notes: str = Field(default="")


class BindingResponse(BaseModel):
    """发布绑定响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_config_id: uuid.UUID
    environment_id: uuid.UUID
    version_id: uuid.UUID
    is_active: bool
    published_at: datetime
    published_by: uuid.UUID | None
    rollback_from_id: uuid.UUID | None
    notes: str
    org_id: uuid.UUID | None


class EnvironmentAgentsResponse(BaseModel):
    """环境内 Agent 列表响应。"""

    environment: str
    data: list[BindingResponse]


class EnvironmentDiffResponse(BaseModel):
    """环境间差异响应。"""

    agent_name: str
    env1: str
    env2: str
    snapshot_env1: dict[str, Any]
    snapshot_env2: dict[str, Any]
