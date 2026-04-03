"""Session 与 Run 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """创建 Session 请求体。"""

    agent_name: str = Field(..., description="绑定的 Agent 名称")
    metadata: dict = Field(default_factory=dict, description="自定义元数据")


class MessageItem(BaseModel):
    """单条消息。"""

    role: str
    content: str
    timestamp: datetime | None = None


class SessionMessageItem(BaseModel):
    """持久化的会话消息（比 MessageItem 更详细）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    agent_name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None
    token_usage: dict | None = None
    created_at: datetime


class SessionMessagesResponse(BaseModel):
    """会话消息列表响应。"""

    session_id: str
    messages: list[SessionMessageItem]
    total: int


class SessionResponse(BaseModel):
    """Session 详情响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    agent_name: str
    status: str
    title: str
    metadata: dict = Field(alias="metadata_")
    messages: list[MessageItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """Session 列表响应。"""

    data: list[SessionResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


class RunConfig(BaseModel):
    """Run 配置。"""

    model_override: str | None = Field(default=None, description="覆盖 Agent 默认模型")
    max_turns: int = Field(default=10, ge=1, le=100, description="最大执行轮次")
    stream: bool = Field(default=True, description="是否流式输出")


class RunRequest(BaseModel):
    """发起 Run 请求体。"""

    input: str = Field(..., min_length=1, description="用户输入消息")
    config: RunConfig = Field(default_factory=RunConfig, description="执行配置")


class TokenUsageResponse(BaseModel):
    """Token 消耗。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RunResponse(BaseModel):
    """非流式 Run 响应。"""

    run_id: str
    status: str
    output: str
    token_usage: TokenUsageResponse
    duration_ms: int
    turn_count: int
    last_agent_name: str | None = None
