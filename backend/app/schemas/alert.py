"""AlertRule / AlertEvent Schema — 告警规则请求/响应。"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# AlertRule
# ---------------------------------------------------------------------------

VALID_METRICS = {"error_rate", "avg_duration_ms", "total_cost", "total_tokens", "trace_count"}
VALID_OPERATORS = {">", ">=", "<", "<=", "=="}
VALID_SEVERITIES = {"critical", "warning", "info"}


class AlertRuleCreate(BaseModel):
    """创建告警规则请求。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="")
    metric: str = Field(..., description="监控指标")
    operator: str = Field(..., description="比较运算符")
    threshold: float = Field(..., description="阈值")
    window_minutes: int = Field(default=60, ge=1, le=1440, description="检测窗口（分钟）")
    agent_name: str | None = Field(default=None, description="监控 Agent，None=全局")
    severity: str = Field(default="warning")
    cooldown_minutes: int = Field(default=30, ge=0, le=1440)
    notification_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        if v not in VALID_METRICS:
            raise ValueError(f"不支持的指标: {v}，可选: {VALID_METRICS}")
        return v

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        if v not in VALID_OPERATORS:
            raise ValueError(f"不支持的运算符: {v}，可选: {VALID_OPERATORS}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in VALID_SEVERITIES:
            raise ValueError(f"不支持的严重级别: {v}，可选: {VALID_SEVERITIES}")
        return v


class AlertRuleUpdate(BaseModel):
    """更新告警规则请求（PATCH 语义）。"""

    name: str | None = None
    description: str | None = None
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    window_minutes: int | None = Field(default=None, ge=1, le=1440)
    agent_name: str | None = None
    severity: str | None = None
    is_enabled: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=1440)
    notification_config: dict[str, Any] | None = None

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_METRICS:
            raise ValueError(f"不支持的指标: {v}")
        return v

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_OPERATORS:
            raise ValueError(f"不支持的运算符: {v}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SEVERITIES:
            raise ValueError(f"不支持的严重级别: {v}")
        return v


class AlertRuleResponse(BaseModel):
    """告警规则响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    metric: str
    operator: str
    threshold: float
    window_minutes: int
    agent_name: str | None
    severity: str
    is_enabled: bool
    cooldown_minutes: int
    notification_config: dict[str, Any]
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertRuleListResponse(BaseModel):
    """告警规则列表响应。"""

    data: list[AlertRuleResponse]
    total: int


# ---------------------------------------------------------------------------
# AlertEvent
# ---------------------------------------------------------------------------


class AlertEventResponse(BaseModel):
    """告警事件响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    metric_value: float
    threshold: float
    severity: str
    agent_name: str | None
    message: str
    resolved_at: datetime | None
    created_at: datetime


class AlertEventListResponse(BaseModel):
    """告警事件列表响应。"""

    data: list[AlertEventResponse]
    total: int


class AlertRuleCheckResponse(BaseModel):
    """告警规则手动检测响应。"""

    triggered: bool
    event_id: uuid.UUID | None = None
    message: str
