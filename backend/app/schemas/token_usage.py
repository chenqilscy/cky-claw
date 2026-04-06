"""Token 审计请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SummaryGroupBy(str, Enum):
    """汇总维度枚举。"""

    agent_model = "agent_model"
    user = "user"
    model = "model"


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
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    timestamp: datetime


class TokenUsageListResponse(BaseModel):
    """Token 消耗记录列表响应。"""

    data: list[TokenUsageLogResponse]
    total: int
    limit: int
    offset: int


class TokenUsageSummaryItem(BaseModel):
    """Token 消耗汇总项（agent_model 维度）。"""

    agent_name: str
    model: str
    total_prompt_tokens: int = Field(description="汇总输入 Token")
    total_completion_tokens: int = Field(description="汇总输出 Token")
    total_tokens: int = Field(description="汇总总 Token")
    total_prompt_cost: float = Field(default=0.0, description="汇总输入成本")
    total_completion_cost: float = Field(default=0.0, description="汇总输出成本")
    total_cost: float = Field(default=0.0, description="汇总总成本")
    call_count: int = Field(description="调用次数")


class TokenUsageByUserItem(BaseModel):
    """Token 消耗汇总项（user 维度）。"""

    user_id: uuid.UUID | None
    total_prompt_tokens: int = Field(description="汇总输入 Token")
    total_completion_tokens: int = Field(description="汇总输出 Token")
    total_tokens: int = Field(description="汇总总 Token")
    total_prompt_cost: float = Field(default=0.0, description="汇总输入成本")
    total_completion_cost: float = Field(default=0.0, description="汇总输出成本")
    total_cost: float = Field(default=0.0, description="汇总总成本")
    call_count: int = Field(description="调用次数")


class TokenUsageByModelItem(BaseModel):
    """Token 消耗汇总项（model 维度）。"""

    model: str
    total_prompt_tokens: int = Field(description="汇总输入 Token")
    total_completion_tokens: int = Field(description="汇总输出 Token")
    total_tokens: int = Field(description="汇总总 Token")
    total_prompt_cost: float = Field(default=0.0, description="汇总输入成本")
    total_completion_cost: float = Field(default=0.0, description="汇总输出成本")
    total_cost: float = Field(default=0.0, description="汇总总成本")
    call_count: int = Field(description="调用次数")


class TokenUsageSummaryResponse(BaseModel):
    """Token 消耗汇总响应。"""

    data: list[TokenUsageSummaryItem | TokenUsageByUserItem | TokenUsageByModelItem]


class TokenUsageTrendItem(BaseModel):
    """Token 消耗趋势数据点（按日聚合）。"""

    date: str = Field(description="日期 YYYY-MM-DD")
    total_tokens: int = Field(description="当日总 Token")
    total_cost: float = Field(default=0.0, description="当日总成本")
    call_count: int = Field(description="当日调用次数")
    model: str | None = Field(default=None, description="模型名（group_by=model 时）")


class TokenUsageTrendResponse(BaseModel):
    """Token 消耗趋势响应。"""

    data: list[TokenUsageTrendItem]
    days: int
