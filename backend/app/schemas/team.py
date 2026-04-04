"""Team 团队请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TeamConfigCreate(BaseModel):
    """创建团队配置请求。"""

    name: str = Field(..., min_length=1, max_length=64, description="团队名称")
    description: str = Field("", max_length=2000, description="团队描述")
    protocol: str = Field("SEQUENTIAL", description="协作协议: SEQUENTIAL / PARALLEL / COORDINATOR")
    member_agent_ids: list[str] = Field(default_factory=list, description="成员 Agent ID 列表")
    coordinator_agent_id: str | None = Field(None, max_length=64, description="Coordinator Agent ID")
    config: dict[str, Any] = Field(default_factory=dict, description="TeamConfig 扩展配置")


class TeamConfigUpdate(BaseModel):
    """更新团队配置请求（部分更新）。"""

    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=2000)
    protocol: str | None = Field(None)
    member_agent_ids: list[str] | None = None
    coordinator_agent_id: str | None = None
    config: dict[str, Any] | None = None


class TeamConfigResponse(BaseModel):
    """团队配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    protocol: str
    member_agent_ids: list[str]
    coordinator_agent_id: str | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TeamConfigListResponse(BaseModel):
    """团队配置列表响应。"""

    data: list[TeamConfigResponse]
    total: int
    limit: int = 20
    offset: int = 0
