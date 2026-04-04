"""AuditLog 审计日志请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """审计日志响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    detail: dict[str, Any]
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    status_code: int | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """审计日志列表响应。"""

    data: list[AuditLogResponse]
    total: int
    limit: int = 20
    offset: int = 0


class AuditLogQuery(BaseModel):
    """审计日志查询参数。"""

    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    action: str | None = None
    resource_type: str | None = None
    user_id: str | None = None
    resource_id: str | None = None
