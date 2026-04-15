"""知识库请求/响应模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""

    name: str = Field(..., min_length=1, max_length=128, description="知识库名称")
    description: str = Field("", max_length=5000, description="描述")
    embedding_model: str = Field("hash-embedding-v1", max_length=128, description="Embedding 模型")
    chunk_strategy: dict[str, Any] = Field(default_factory=dict, description="分块策略")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求。"""

    name: str | None = Field(None, min_length=1, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=5000, description="描述")
    embedding_model: str | None = Field(None, max_length=128, description="Embedding 模型")
    chunk_strategy: dict[str, Any] | None = Field(None, description="分块策略")
    metadata: dict[str, Any] | None = Field(None, description="自定义元数据")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    description: str
    embedding_model: str
    chunk_strategy: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应。"""

    data: list[KnowledgeBaseResponse]
    total: int
    limit: int = 20
    offset: int = 0


class KnowledgeDocumentResponse(BaseModel):
    """知识库文档响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    media_type: str
    size_bytes: int
    status: str
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求。"""

    query: str = Field(..., min_length=1, max_length=500, description="检索问题")
    top_k: int = Field(5, ge=1, le=20, description="返回分块数量")
    min_score: float = Field(0.0, ge=-1.0, le=1.0, description="最低相似度")


class KnowledgeSearchItem(BaseModel):
    """检索结果项。"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """知识库检索响应。"""

    knowledge_base_id: uuid.UUID
    query: str
    results: list[KnowledgeSearchItem]
