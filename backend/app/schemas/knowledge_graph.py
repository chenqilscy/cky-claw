"""知识图谱请求/响应模型。"""

from __future__ import annotations
import uuid
from datetime import datetime

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

class BuildGraphRequest(BaseModel):
    """触发图谱构建请求。"""

    extract_model: str = Field("gpt-4o-mini", description="用于抽取的 LLM 模型")
    entity_types: list[str] = Field(default_factory=list, description="关注的实体类型（空=自动检测）")
    chunk_size: int = Field(1024, ge=256, le=4096, description="分块大小")
    overlap: int = Field(128, ge=0, le=512, description="分块重叠")
    resolution: float = Field(1.0, gt=0.0, description="Leiden 社区检测分辨率")

class GraphBuildStatusResponse(BaseModel):
    """图谱构建状态响应。"""

    task_id: str
    status: str  # pending / processing / completed / failed
    progress: float = 0.0
    entity_count: int = 0
    relation_count: int = 0
    community_count: int = 0
    error: str | None = None

class EntityResponse(BaseModel):
    """实体响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    name: str
    entity_type: str
    description: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float
    confidence_label: str
    content_hash: str = ""
    created_at: datetime

class EntityListResponse(BaseModel):
    """实体列表响应。"""

    data: list[EntityResponse]
    total: int
    limit: int = 50
    offset: int = 0

class RelationResponse(BaseModel):
    """关系响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relation_type: str
    description: str
    weight: float
    confidence: float
    confidence_label: str

class RelationListResponse(BaseModel):
    """关系列表响应。"""

    data: list[RelationResponse]
    total: int
    limit: int = 50
    offset: int = 0

class CommunityResponse(BaseModel):
    """社区响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    name: str
    summary: str
    entity_count: int = 0
    level: int
    parent_community_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

class CommunityListResponse(BaseModel):
    """社区列表响应。"""

    data: list[CommunityResponse]
    total: int
    limit: int = 50
    offset: int = 0

class GraphDataResponse(BaseModel):
    """图谱可视化数据响应。"""

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)

class GraphSearchRequest(BaseModel):
    """图谱检索请求。"""

    query: str = Field(..., min_length=1, max_length=500, description="检索查询")
    top_k: int = Field(10, ge=1, le=50, description="返回结果数量")
    max_depth: int = Field(2, ge=1, le=4, description="关系遍历深度")
    search_mode: str = Field("hybrid", pattern=r"^(entity|traverse|community|hybrid)$")

class GraphSearchResultItem(BaseModel):
    """图谱检索结果项。"""

    entity: EntityResponse | None = None
    relation: RelationResponse | None = None
    community: CommunityResponse | None = None
    score: float
    source: str  # entity_match / relation_traverse / community_summary

class GraphSearchResponse(BaseModel):
    """图谱检索响应。"""

    knowledge_base_id: uuid.UUID
    query: str
    results: list[GraphSearchResultItem]
