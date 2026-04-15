"""Debug Session 请求/响应 Schema。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class DebugSessionCreate(BaseModel):
    """创建调试会话请求。"""

    agent_id: uuid.UUID = Field(..., description="被调试的 Agent ID")
    input_message: str = Field(..., min_length=1, max_length=4096, description="调试输入消息")
    mode: Literal["step_turn", "step_tool", "continue"] = Field(default="step_turn", description="调试模式")

    model_config = {"json_schema_extra": {"examples": [{"agent_id": "550e8400-e29b-41d4-a716-446655440000", "input_message": "你好", "mode": "step_turn"}]}}


class DebugSessionResponse(BaseModel):
    """调试会话响应。"""

    id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    user_id: uuid.UUID
    state: str
    mode: str
    input_message: str
    current_turn: int
    current_agent_name: str
    pause_context: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class DebugSessionListResponse(BaseModel):
    """调试会话列表响应。"""

    items: list[DebugSessionResponse]
    total: int


class DebugActionRequest(BaseModel):
    """调试控制操作请求（step/continue/stop）。"""

    pass


class DebugContextResponse(BaseModel):
    """调试上下文响应 — 暂停时的详细状态。"""

    turn: int
    agent_name: str
    reason: str
    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
    last_llm_response: dict[str, Any] | None = None
    last_tool_calls: list[dict[str, Any]] | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    paused_at: str | None = None


class DebugEventMessage(BaseModel):
    """WebSocket 事件消息。"""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
