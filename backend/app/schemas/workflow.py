"""Workflow 工作流请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Nested types — Step / Edge
# ---------------------------------------------------------------------------


class StepIOSchema(BaseModel):
    """步骤输入/输出映射。"""

    input_keys: dict[str, str] = Field(default_factory=dict)
    output_keys: dict[str, str] = Field(default_factory=dict)


class RetryConfigSchema(BaseModel):
    """步骤重试配置。"""

    max_retries: int = Field(2, ge=0, le=10)
    delay_seconds: float = Field(1.0, ge=0)
    backoff_multiplier: float = Field(2.0, ge=1.0)


class StepSchema(BaseModel):
    """步骤定义。"""

    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field("", max_length=128)
    type: str = Field("agent", description="agent|parallel|conditional|loop")
    agent_name: str | None = Field(None, max_length=64)
    prompt_template: str | None = Field(None, max_length=10000)
    max_turns: int = Field(10, ge=1, le=100)
    io: StepIOSchema = Field(default_factory=StepIOSchema)
    retry_config: RetryConfigSchema | None = None
    timeout: float | None = None
    # Parallel
    parallel_step_ids: list[str] = Field(default_factory=list)
    # Conditional
    branches: list[dict[str, str]] = Field(default_factory=list)
    default_target_step_id: str | None = None
    # Loop
    condition: str | None = None
    body_step_ids: list[str] = Field(default_factory=list)
    max_iterations: int = Field(100, ge=1, le=1000)


class EdgeSchema(BaseModel):
    """DAG 边。"""

    id: str = Field(..., min_length=1, max_length=64)
    source_step_id: str = Field(..., min_length=1)
    target_step_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    """创建工作流请求体。"""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*$", description="工作流唯一名称")
    description: str = Field("", max_length=5000, description="描述")
    steps: list[StepSchema] = Field(default_factory=list, description="步骤列表")
    edges: list[EdgeSchema] = Field(default_factory=list, description="边列表")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="输入 Schema")
    output_keys: list[str] = Field(default_factory=list, description="输出键")
    timeout: float | None = Field(None, ge=0, description="全局超时（秒）")
    guardrail_names: list[str] = Field(default_factory=list, description="护栏名称列表")
    metadata: dict = Field(default_factory=dict, description="自定义元数据")


class WorkflowUpdate(BaseModel):
    """更新工作流请求体。"""

    description: str | None = Field(None, max_length=5000)
    steps: list[StepSchema] | None = None
    edges: list[EdgeSchema] | None = None
    input_schema: dict[str, Any] | None = None
    output_keys: list[str] | None = None
    timeout: float | None = Field(None, ge=0)
    guardrail_names: list[str] | None = None
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class WorkflowResponse(BaseModel):
    """工作流响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    description: str
    steps: list[dict]
    edges: list[dict]
    input_schema: dict[str, Any]
    output_keys: list[str]
    timeout: float | None
    guardrail_names: list[str]
    metadata: dict = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class WorkflowListResponse(BaseModel):
    """工作流列表响应。"""

    data: list[WorkflowResponse]
    total: int
    limit: int = 20
    offset: int = 0


class WorkflowValidateResponse(BaseModel):
    """工作流验证结果。"""

    valid: bool
    errors: list[str] = Field(default_factory=list)
