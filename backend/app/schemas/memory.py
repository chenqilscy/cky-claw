"""Memory 记忆条目请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MemoryTypeEnum(str, Enum):
    """记忆类型。"""

    USER_PROFILE = "user_profile"
    HISTORY_SUMMARY = "history_summary"
    STRUCTURED_FACT = "structured_fact"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class MemoryCreate(BaseModel):
    """创建记忆条目请求体。"""

    type: MemoryTypeEnum = Field(..., description="记忆类型")
    content: str = Field(..., min_length=1, max_length=10000, description="记忆内容")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="置信度")
    user_id: str = Field(..., min_length=1, max_length=128, description="用户标识")
    agent_name: str | None = Field(None, max_length=64, description="Agent 名称")
    source_session_id: str | None = Field(None, max_length=128, description="来源会话 ID")
    metadata: dict = Field(default_factory=dict, description="自定义元数据")


class MemoryUpdate(BaseModel):
    """更新记忆条目请求体。"""

    content: str | None = Field(None, min_length=1, max_length=10000, description="记忆内容")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="置信度")
    type: MemoryTypeEnum | None = Field(None, description="记忆类型")
    metadata: dict | None = Field(None, description="自定义元数据")


class MemorySearchRequest(BaseModel):
    """搜索记忆请求体。"""

    user_id: str = Field(..., min_length=1, description="用户标识")
    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    limit: int = Field(10, ge=1, le=100, description="返回上限")


class MemoryDecayRequest(BaseModel):
    """置信度衰减请求体。"""

    before: datetime = Field(..., description="仅影响此时间之前的条目")
    rate: float = Field(0.01, gt=0.0, le=1.0, description="衰减量")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class MemoryResponse(BaseModel):
    """记忆条目响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: str
    type: MemoryTypeEnum
    content: str
    confidence: float
    agent_name: str | None = None
    source_session_id: str | None = None
    metadata: dict = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    """记忆列表响应。"""

    data: list[MemoryResponse]
    total: int
    limit: int = 20
    offset: int = 0


class MemoryDecayResponse(BaseModel):
    """衰减操作响应。"""

    affected: int
