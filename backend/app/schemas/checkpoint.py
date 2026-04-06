"""Checkpoint 请求/响应 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CheckpointResponse(BaseModel):
    """Checkpoint 详情响应。"""

    checkpoint_id: str
    run_id: str
    turn_count: int
    current_agent_name: str
    messages: list[dict[str, Any]]
    token_usage: dict[str, int]
    context: dict[str, Any]
    created_at: datetime


class CheckpointListResponse(BaseModel):
    """Checkpoint 列表响应。"""

    data: list[CheckpointResponse]
    total: int
