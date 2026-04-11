"""Mailbox 请求/响应 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MailboxSendRequest(BaseModel):
    """发送消息请求。"""

    run_id: str = Field(..., description="所属运行 ID")
    from_agent: str = Field(..., description="发送方 Agent 名称")
    to_agent: str = Field(..., description="接收方 Agent 名称")
    content: str = Field(..., description="消息内容")
    message_type: str = Field(default="handoff", description="消息类型")
    metadata: dict[str, Any] = Field(default_factory=dict)


class MailboxMessageResponse(BaseModel):
    """消息响应。"""

    id: uuid.UUID
    run_id: str
    from_agent: str
    to_agent: str
    content: str
    message_type: str
    is_read: bool
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_", validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class MailboxListResponse(BaseModel):
    """消息列表响应。"""

    data: list[MailboxMessageResponse]
    total: int
