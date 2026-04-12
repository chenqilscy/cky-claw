"""A2A 协议 Pydantic Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent Card
# ---------------------------------------------------------------------------
class A2AAgentCardCreate(BaseModel):
    """创建 Agent Card 请求。"""

    agent_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    url: str = ""
    version: str = "1.0.0"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    authentication: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AAgentCardUpdate(BaseModel):
    """更新 Agent Card 请求。"""

    name: str | None = None
    description: str | None = None
    url: str | None = None
    version: str | None = None
    capabilities: dict[str, Any] | None = None
    skills: list[dict[str, Any]] | None = None
    authentication: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class A2AAgentCardResponse(BaseModel):
    """Agent Card 响应。"""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    description: str
    url: str
    version: str
    capabilities: dict[str, Any]
    skills: list[dict[str, Any]]
    authentication: dict[str, Any]
    metadata_: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime


class A2AAgentCardListResponse(BaseModel):
    """Agent Card 列表响应。"""

    data: list[A2AAgentCardResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
class A2ATaskCreate(BaseModel):
    """创建 A2A Task 请求。"""

    agent_card_id: uuid.UUID
    input_messages: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskResponse(BaseModel):
    """A2A Task 响应。"""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    agent_card_id: uuid.UUID
    status: str
    input_messages: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    history: list[dict[str, Any]]
    metadata_: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime


class A2ATaskListResponse(BaseModel):
    """A2A Task 列表响应。"""

    data: list[A2ATaskResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Discovery (/.well-known/agent.json 格式)
# ---------------------------------------------------------------------------
class A2ADiscoveryResponse(BaseModel):
    """A2A 发现协议响应（简化 Agent Card）。"""

    name: str
    description: str
    url: str
    version: str
    capabilities: dict[str, Any]
    skills: list[dict[str, Any]]
    authentication: dict[str, Any]
    defaultInputModes: list[str] = ["text/plain"]
    defaultOutputModes: list[str] = ["text/plain"]
