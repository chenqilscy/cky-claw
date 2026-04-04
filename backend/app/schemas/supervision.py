"""监督面板请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 会话状态枚举
# ---------------------------------------------------------------------------


class SessionStatus(str, Enum):
    """会话状态。"""

    active = "active"
    paused = "paused"
    completed = "completed"


# ---------------------------------------------------------------------------
# 活跃会话
# ---------------------------------------------------------------------------


class SupervisionSessionItem(BaseModel):
    """活跃会话列表项。"""

    session_id: uuid.UUID
    agent_name: str
    status: str
    title: str
    token_used: int = Field(default=0, description="累计消耗 Token 数")
    call_count: int = Field(default=0, description="累计调用次数")
    created_at: datetime
    updated_at: datetime


class SupervisionSessionListResponse(BaseModel):
    """活跃会话列表响应。"""

    data: list[SupervisionSessionItem]
    total: int
    limit: int = 20
    offset: int = 0


class MessageItem(BaseModel):
    """消息项。"""

    role: str
    content: str
    timestamp: datetime | None = None


class SupervisionSessionDetail(SupervisionSessionItem):
    """会话详情（含消息历史）。"""

    messages: list[MessageItem] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 暂停 / 恢复
# ---------------------------------------------------------------------------


class PauseRequest(BaseModel):
    """暂停会话请求。"""

    reason: str = Field(default="", description="暂停原因")


class ResumeRequest(BaseModel):
    """恢复会话请求。"""

    injected_instructions: str = Field(default="", description="恢复时注入的指令")


class SupervisionActionResponse(BaseModel):
    """监督操作响应。"""

    session_id: uuid.UUID
    status: str
    message: str
