"""ScheduledTask Schema — 定时任务请求/响应。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScheduledTaskCreate(BaseModel):
    """创建定时任务请求。"""

    name: str = Field(..., min_length=1, max_length=128, description="任务名称")
    description: str = Field(default="", description="任务描述")
    agent_id: uuid.UUID = Field(..., description="关联 Agent ID")
    cron_expr: str = Field(..., min_length=1, max_length=128, description="Cron 表达式")
    input_text: str = Field(default="", description="Agent 输入文本")

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"无效的 Cron 表达式: {v}")
        return v


class ScheduledTaskUpdate(BaseModel):
    """更新定时任务请求（PATCH 语义）。"""

    name: str | None = None
    description: str | None = None
    cron_expr: str | None = None
    input_text: str | None = None
    is_enabled: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"无效的 Cron 表达式: {v}")
        return v


class ScheduledTaskResponse(BaseModel):
    """定时任务响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    agent_id: uuid.UUID
    cron_expr: str
    input_text: str
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScheduledTaskListResponse(BaseModel):
    """定时任务列表响应。"""

    data: list[ScheduledTaskResponse]
    total: int
