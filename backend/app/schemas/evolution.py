"""进化建议 Pydantic Schema。"""

from __future__ import annotations
import uuid
from datetime import datetime

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VALID_PROPOSAL_TYPES = {"instructions", "tools", "guardrails", "model", "memory"}
_VALID_STATUSES = {"pending", "approved", "rejected", "applied", "rolled_back"}

class EvolutionProposalCreate(BaseModel):
    """创建进化建议请求体。"""

    agent_name: str = Field(..., min_length=1, max_length=64, description="目标 Agent 名称")
    proposal_type: str = Field(..., description="建议类型")
    trigger_reason: str = Field(default="", description="触发原因")
    current_value: dict[str, Any] | None = Field(default=None, description="当前配置值")
    proposed_value: dict[str, Any] | None = Field(default=None, description="建议的新配置值")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0~1")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    @field_validator("proposal_type")
    @classmethod
    def validate_proposal_type(cls, v: str) -> str:
        """校验 proposal_type 为合法枚举值。"""
        if v not in _VALID_PROPOSAL_TYPES:
            msg = f"proposal_type 必须是 {_VALID_PROPOSAL_TYPES} 之一"
            raise ValueError(msg)
        return v

class EvolutionProposalUpdate(BaseModel):
    """更新进化建议请求体（PATCH 语义）。"""

    status: str | None = None
    eval_before: float | None = None
    eval_after: float | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """校验 status 为合法枚举值。"""
        if v is not None and v not in _VALID_STATUSES:
            msg = f"status 必须是 {_VALID_STATUSES} 之一"
            raise ValueError(msg)
        return v

class EvolutionProposalResponse(BaseModel):
    """进化建议响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    agent_name: str
    proposal_type: str
    status: str
    trigger_reason: str
    current_value: dict[str, Any] | None
    proposed_value: dict[str, Any] | None
    confidence_score: float
    eval_before: float | None
    eval_after: float | None
    applied_at: datetime | None
    rolled_back_at: datetime | None
    metadata: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime

class EvolutionProposalListResponse(BaseModel):
    """进化建议列表响应。"""

    data: list[EvolutionProposalResponse]
    total: int
    limit: int
    offset: int

# ────────────────────────────────────────────────────────────────
# 进化信号 Schema
# ────────────────────────────────────────────────────────────────

_VALID_SIGNAL_TYPES = {"evaluation", "feedback", "tool_performance", "guardrail", "token_usage"}

class EvolutionSignalCreate(BaseModel):
    """上报进化信号请求体。"""

    agent_name: str = Field(..., min_length=1, max_length=64, description="Agent 名称")
    signal_type: str = Field(..., description="信号类型")
    tool_name: str | None = Field(default=None, max_length=128, description="工具名称")
    call_count: int = Field(default=0, ge=0, description="调用次数")
    success_count: int = Field(default=0, ge=0, description="成功次数")
    failure_count: int = Field(default=0, ge=0, description="失败次数")
    avg_duration_ms: float = Field(default=0.0, ge=0.0, description="平均耗时 ms")
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0, description="综合评分")
    negative_rate: float | None = Field(default=None, ge=0.0, le=1.0, description="负反馈率")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    @field_validator("signal_type")
    @classmethod
    def validate_signal_type(cls, v: str) -> str:
        """校验 signal_type 为合法枚举值。"""
        if v not in _VALID_SIGNAL_TYPES:
            msg = f"signal_type 必须是 {_VALID_SIGNAL_TYPES} 之一"
            raise ValueError(msg)
        return v

class EvolutionSignalResponse(BaseModel):
    """进化信号响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    agent_name: str
    signal_type: str
    tool_name: str | None
    call_count: int
    success_count: int
    failure_count: int
    avg_duration_ms: float
    overall_score: float | None
    negative_rate: float | None
    metadata: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime

class EvolutionSignalListResponse(BaseModel):
    """进化信号列表响应。"""

    data: list[EvolutionSignalResponse]
    total: int
    limit: int
    offset: int

class EvolutionAnalyzeResponse(BaseModel):
    """策略分析响应。"""

    proposals_created: int = Field(description="生成的建议数量")
    proposals: list[EvolutionProposalResponse] = Field(description="生成的建议列表")

class RollbackCheckRequest(BaseModel):
    """回滚检查请求体。"""

    eval_after: float = Field(..., ge=0.0, le=1.0, description="应用后的最新评分")
    rollback_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="回滚阈值")

class RollbackCheckResponse(BaseModel):
    """回滚检查响应。"""

    model_config = ConfigDict(from_attributes=True)

    rolled_back: bool = Field(description="是否触发了回滚")
    proposal: EvolutionProposalResponse = Field(description="更新后的建议记录")

class ScanRollbackResponse(BaseModel):
    """批量回滚扫描响应。"""

    rolled_back_count: int = Field(description="被回滚的建议数量")
    proposals: list[EvolutionProposalResponse] = Field(description="被回滚的建议列表")
