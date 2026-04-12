"""Session 与 Run 请求/响应模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """创建 Session 请求体。"""

    agent_name: str = Field(..., description="绑定的 Agent 名称")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")


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
    content_blocks: list[dict[str, Any]] | None = None
    agent_name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    token_usage: dict[str, Any] | None = None
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
    metadata: dict[str, Any] = Field(alias="metadata_")
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
    memory_user_id: str | None = Field(default=None, max_length=128, description="记忆注入用户 ID。设置后自动检索并注入相关记忆到上下文。")

    # S3: CircuitBreaker 配置
    circuit_breaker_enabled: bool = Field(default=False, description="是否启用 LLM 调用熔断器")
    cb_failure_threshold: int = Field(default=5, ge=1, le=50, description="连续失败 N 次后打开熔断器")
    cb_recovery_timeout: float = Field(default=30.0, gt=0, le=300, description="OPEN 状态恢复超时（秒）")

    # S3: FallbackChain 配置
    fallback_provider_ids: list[str] | None = Field(default=None, description="降级 Provider ID 列表（按优先级排序）")

    # S3: ToolMiddleware 配置
    tool_cache_enabled: bool = Field(default=False, description="是否启用工具结果缓存中间件")
    tool_cache_ttl: float = Field(default=60.0, gt=0, le=3600, description="工具缓存 TTL（秒）")
    tool_loop_guard_enabled: bool = Field(default=False, description="是否启用循环调用检测中间件")
    tool_loop_guard_max_repeats: int = Field(default=3, ge=1, le=20, description="循环调用最大重复次数")
    tool_rate_limit_enabled: bool = Field(default=False, description="是否启用工具频率限制中间件")
    tool_rate_limit_max_calls: int = Field(default=10, ge=1, le=1000, description="频率限制窗口内最大调用次数")
    tool_rate_limit_window: float = Field(default=60.0, gt=0, le=3600, description="频率限制时间窗口（秒）")

    # S4: EventJournal 配置
    event_journal_enabled: bool = Field(default=False, description="是否启用事件日志（用于回放和审计）")


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
