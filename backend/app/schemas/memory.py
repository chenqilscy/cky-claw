"""Memory 记忆条目请求/响应模型。"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class MemoryTypeEnum(StrEnum):
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
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    embedding: list[float] | None = Field(None, description="向量表示")
    tags: list[str] = Field(default_factory=list, description="分类标签")


class MemoryUpdate(BaseModel):
    """更新记忆条目请求体。"""

    content: str | None = Field(None, min_length=1, max_length=10000, description="记忆内容")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="置信度")
    type: MemoryTypeEnum | None = Field(None, description="记忆类型")
    metadata: dict[str, Any] | None = Field(None, description="自定义元数据")
    embedding: list[float] | None = Field(None, description="向量表示")
    tags: list[str] | None = Field(None, description="分类标签")


class MemorySearchRequest(BaseModel):
    """搜索记忆请求体。"""

    user_id: str = Field(..., min_length=1, description="用户标识")
    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    limit: int = Field(10, ge=1, le=100, description="返回上限")


class MemoryTagSearchRequest(BaseModel):
    """按标签搜索记忆请求体。"""

    user_id: str = Field(..., min_length=1, description="用户标识")
    tags: list[str] = Field(..., min_length=1, description="标签列表（OR 匹配）")
    limit: int = Field(10, ge=1, le=100, description="返回上限")


class MemoryDecayModeEnum(StrEnum):
    """衰减模式。"""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class MemoryDecayRequest(BaseModel):
    """置信度衰减请求体。"""

    before: datetime = Field(..., description="仅影响此时间之前的条目")
    rate: float = Field(0.01, gt=0.0, le=1.0, description="衰减参数（线性:固定值, 指数:λ系数）")
    mode: MemoryDecayModeEnum = Field(
        MemoryDecayModeEnum.LINEAR,
        description="衰减模式: linear（线性）/ exponential（指数-艾宾浩斯遗忘曲线）",
    )


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
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    embedding: list[float] | None = None
    tags: list[str] = Field(default_factory=list)
    access_count: int = 0
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


class MemoryCountResponse(BaseModel):
    """记忆计数响应。"""

    user_id: str
    count: int
