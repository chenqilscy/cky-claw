"""Agent 版本管理请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentVersionResponse(BaseModel):
    """Agent 版本详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_config_id: uuid.UUID
    version: int
    snapshot: dict
    change_summary: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class AgentVersionListResponse(BaseModel):
    """Agent 版本列表响应。"""

    data: list[AgentVersionResponse]
    total: int


class AgentVersionDiffResponse(BaseModel):
    """Agent 版本对比响应。"""

    version_a: int
    version_b: int
    snapshot_a: dict
    snapshot_b: dict


class AgentRollbackRequest(BaseModel):
    """回滚请求体。"""

    change_summary: str | None = Field(default=None, max_length=512, description="回滚原因")
