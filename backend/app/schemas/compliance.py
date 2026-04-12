"""Compliance 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- 数据分类标签 ---

class ClassificationLabelCreate(BaseModel):
    """创建数据分类标签。"""

    resource_type: str = Field(..., max_length=64)
    resource_id: str = Field(..., max_length=128)
    classification: str = Field(..., pattern="^(public|internal|sensitive|pii|phi)$")
    reason: str = Field("", max_length=500)


class ClassificationLabelResponse(BaseModel):
    """数据分类标签响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: str
    classification: str
    auto_detected: bool
    reason: str
    created_at: datetime


class ClassificationLabelListResponse(BaseModel):
    """标签列表响应。"""

    data: list[ClassificationLabelResponse]
    total: int


# --- 数据保留策略 ---

class RetentionPolicyCreate(BaseModel):
    """创建保留策略。"""

    resource_type: str = Field(..., max_length=64)
    classification: str = Field(..., pattern="^(public|internal|sensitive|pii|phi)$")
    retention_days: int = Field(..., ge=1, le=3650)


class RetentionPolicyUpdate(BaseModel):
    """更新保留策略。"""

    retention_days: int | None = Field(None, ge=1, le=3650)
    status: str | None = Field(None, pattern="^(active|expired|deleted)$")


class RetentionPolicyResponse(BaseModel):
    """保留策略响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    classification: str
    retention_days: int
    status: str
    last_executed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RetentionPolicyListResponse(BaseModel):
    """保留策略列表响应。"""

    data: list[RetentionPolicyResponse]
    total: int


# --- Right-to-Erasure ---

class ErasureRequestCreate(BaseModel):
    """创建删除请求。"""

    target_user_id: uuid.UUID


class ErasureRequestResponse(BaseModel):
    """删除请求响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_user_id: uuid.UUID
    target_user_id: uuid.UUID
    status: str
    scanned_resources: int
    deleted_resources: int
    report: dict | None = None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ErasureRequestListResponse(BaseModel):
    """删除请求列表响应。"""

    data: list[ErasureRequestResponse]
    total: int


# --- SOC2 控制点 ---

class ControlPointCreate(BaseModel):
    """创建控制点。"""

    control_id: str = Field(..., max_length=32)
    category: str = Field(..., max_length=64)
    description: str
    implementation: str = ""
    evidence_links: dict | None = None


class ControlPointUpdate(BaseModel):
    """更新控制点。"""

    implementation: str | None = None
    evidence_links: dict | None = None
    is_satisfied: bool | None = None


class ControlPointResponse(BaseModel):
    """控制点响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: str
    category: str
    description: str
    implementation: str
    evidence_links: dict | None
    is_satisfied: bool
    created_at: datetime
    updated_at: datetime


class ControlPointListResponse(BaseModel):
    """控制点列表响应。"""

    data: list[ControlPointResponse]
    total: int


# --- 合规仪表盘 ---

class ComplianceDashboardResponse(BaseModel):
    """合规仪表盘汇总。"""

    total_control_points: int
    satisfied_control_points: int
    satisfaction_rate: float
    active_retention_policies: int
    pending_erasure_requests: int
    classification_summary: dict[str, int]
