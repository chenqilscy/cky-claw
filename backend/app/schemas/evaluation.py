"""Agent 评估请求/响应模型。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

VALID_EVAL_METHODS = {"manual", "auto", "llm_judge"}


class RunEvaluationCreate(BaseModel):
    """创建运行评估。"""

    run_id: str = Field(..., description="关联的运行 ID")
    agent_id: uuid.UUID | None = Field(default=None, description="关联的 Agent ID")
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    helpfulness: float = Field(default=0.0, ge=0.0, le=1.0)
    safety: float = Field(default=0.0, ge=0.0, le=1.0)
    efficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_usage: float = Field(default=0.0, ge=0.0, le=1.0)
    eval_method: str = Field(default="manual", description="评估方式：manual/auto/llm_judge")
    evaluator: str = Field(default="", description="评估者")
    comment: str = Field(default="", description="评语")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEvaluationResponse(BaseModel):
    """运行评估响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: str
    agent_id: uuid.UUID | None
    accuracy: float
    relevance: float
    coherence: float
    helpfulness: float
    safety: float
    efficiency: float
    tool_usage: float
    overall_score: float
    eval_method: str
    evaluator: str
    comment: str
    created_at: datetime


class RunEvaluationListResponse(BaseModel):
    """运行评估列表。"""

    data: list[RunEvaluationResponse]
    total: int
    limit: int = 20
    offset: int = 0


class RunFeedbackCreate(BaseModel):
    """创建用户反馈。"""

    run_id: str = Field(..., description="关联的运行 ID")
    rating: int = Field(..., ge=-1, le=1, description="评分：-1(差)/0(中)/1(好)")
    comment: str = Field(default="", description="反馈内容")
    tags: list[str] = Field(default_factory=list, description="标签")


class RunFeedbackResponse(BaseModel):
    """用户反馈响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: str
    user_id: uuid.UUID | None
    rating: int
    comment: str
    tags: list[Any] | dict[str, Any]
    created_at: datetime


class RunFeedbackListResponse(BaseModel):
    """用户反馈列表。"""

    data: list[RunFeedbackResponse]
    total: int
    limit: int = 20
    offset: int = 0


class AgentQualitySummary(BaseModel):
    """Agent 质量度量汇总。"""

    agent_id: uuid.UUID
    eval_count: int = 0
    avg_accuracy: float = 0.0
    avg_relevance: float = 0.0
    avg_coherence: float = 0.0
    avg_helpfulness: float = 0.0
    avg_safety: float = 0.0
    avg_efficiency: float = 0.0
    avg_tool_usage: float = 0.0
    avg_overall: float = 0.0
    feedback_count: int = 0
    positive_rate: float = 0.0


class AutoEvaluateRequest(BaseModel):
    """自动评估请求（提供上下文）。"""

    run_id: str = Field(..., description="运行 ID")
    agent_id: uuid.UUID | None = Field(default=None, description="Agent ID")
    user_input: str = Field(..., description="用户输入文本")
    agent_output: str = Field(..., description="Agent 输出文本")
    duration_ms: int = Field(default=0, ge=0, description="执行时间（ms）")
    total_tokens: int = Field(default=0, ge=0, description="总 Token 消耗")
    turn_count: int = Field(default=0, ge=0, description="对话轮次")
    last_agent: str = Field(default="", description="最终处理 Agent")
    judge_model: str | None = Field(default=None, description="Judge LLM 模型（默认 deepseek-chat）")
