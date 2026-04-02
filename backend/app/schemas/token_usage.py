"""Token 审计请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenUsageLogResponse(BaseModel):
    """单条 Token 消耗记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trace_id: str
    span_id: str
    session_id: uuid.UUID | None
    user_id: uuid.UUID | None
    agent_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: datetime


class TokenUsageListResponse(BaseModel):
    """Token 消耗记录列表响应。"""

    data: list[TokenUsageLogResponse]
    total: int
    limit: int
    offset: int


class TokenUsageSummaryItem(BaseModel):
    """Token 消耗汇总项。"""

    agent_name: str
    model: str
    total_prompt_tokens: int = Field(description="汇总输入 Token")
    total_completion_tokens: int = Field(description="汇总输出 Token")
    total_tokens: int = Field(description="汇总总 Token")
    call_count: int = Field(description="调用次数")


class TokenUsageSummaryResponse(BaseModel):
    """Token 消耗汇总响应。"""

    data: list[TokenUsageSummaryItem]
