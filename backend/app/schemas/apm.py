"""APM 仪表盘 Schema。"""

from __future__ import annotations

from pydantic import BaseModel


class ApmOverview(BaseModel):
    """APM 总览指标。"""

    total_traces: int = 0
    total_spans: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_duration_ms: float = 0.0
    error_rate: float = 0.0


class AgentRankItem(BaseModel):
    """Agent 调用排名项。"""

    agent_name: str
    call_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_duration_ms: float = 0.0
    error_count: int = 0


class ModelUsageItem(BaseModel):
    """模型使用分布项。"""

    model: str
    call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class DailyTrendItem(BaseModel):
    """每日趋势项。"""

    date: str
    traces: int = 0
    tokens: int = 0
    cost: float = 0.0


class ToolUsageItem(BaseModel):
    """工具调用排名项。"""

    tool_name: str
    call_count: int = 0
    avg_duration_ms: float = 0.0


class ApmDashboardResponse(BaseModel):
    """APM 仪表盘完整响应。"""

    overview: ApmOverview
    agent_ranking: list[AgentRankItem]
    model_usage: list[ModelUsageItem]
    daily_trend: list[DailyTrendItem]
    tool_usage: list[ToolUsageItem]
