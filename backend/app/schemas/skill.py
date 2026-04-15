"""Skill 技能知识包请求/响应模型。"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class SkillCategoryEnum(StrEnum):
    """技能分类。"""

    PUBLIC = "public"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class SkillCreate(BaseModel):
    """创建技能请求体。"""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*$", description="技能唯一名称")
    version: str = Field("1.0.0", max_length=32, description="语义化版本号")
    description: str = Field("", max_length=2000, description="技能描述")
    content: str = Field(..., min_length=1, max_length=50000, description="SKILL.md 主知识内容")
    category: SkillCategoryEnum = Field(SkillCategoryEnum.CUSTOM, description="技能分类")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    applicable_agents: list[str] = Field(default_factory=list, description="适用 Agent 名称列表")
    author: str = Field("", max_length=64, description="作者")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")


class SkillUpdate(BaseModel):
    """更新技能请求体。"""

    version: str | None = Field(None, max_length=32, description="语义化版本号")
    description: str | None = Field(None, max_length=2000, description="技能描述")
    content: str | None = Field(None, min_length=1, max_length=50000, description="SKILL.md 主知识内容")
    category: SkillCategoryEnum | None = Field(None, description="技能分类")
    tags: list[str] | None = Field(None, description="标签列表")
    applicable_agents: list[str] | None = Field(None, description="适用 Agent 名称列表")
    author: str | None = Field(None, max_length=64, description="作者")
    metadata: dict[str, Any] | None = Field(None, description="自定义元数据")


class SkillSearchRequest(BaseModel):
    """搜索技能请求体。"""

    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    category: SkillCategoryEnum | None = Field(None, description="按分类筛选")
    limit: int = Field(20, ge=1, le=100, description="返回上限")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class SkillResponse(BaseModel):
    """技能响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    version: str
    description: str
    content: str
    category: SkillCategoryEnum
    tags: list[str]
    applicable_agents: list[str]
    author: str
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    """技能列表响应。"""

    data: list[SkillResponse]
    total: int
    limit: int = 20
    offset: int = 0
