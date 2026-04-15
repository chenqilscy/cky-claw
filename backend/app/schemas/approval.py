"""Approval 审批请求 Schema。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class ApprovalResolveRequest(BaseModel):
    """审批操作请求体。"""

    action: str = Field(..., description="审批动作: approve / reject")
    comment: str = Field(default="", description="审批意见")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"approve", "reject"}
        if v not in allowed:
            raise ValueError(f"action 必须是 {allowed} 之一")
        return v


class ApprovalResponse(BaseModel):
    """审批请求响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    run_id: str
    agent_name: str
    trigger: str
    content: dict[str, Any]
    status: str
    comment: str
    resolved_at: datetime | None = None
    created_at: datetime


class ApprovalListResponse(BaseModel):
    """审批请求列表响应。"""

    data: list[ApprovalResponse]
    total: int
    limit: int = 20
    offset: int = 0
