"""知识库 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import get_org_id
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeDocumentResponse,
    KnowledgeSearchItem,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services import knowledge_base as kb_service

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=201,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeBaseResponse:
    """创建知识库。"""
    row = await kb_service.create_knowledge_base(db, data, org_id=org_id)
    return KnowledgeBaseResponse.model_validate(row)


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def list_knowledge_bases(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeBaseListResponse:
    """查询知识库列表。"""
    rows, total = await kb_service.list_knowledge_bases(db, limit=limit, offset=offset, org_id=org_id)
    return KnowledgeBaseListResponse(
        data=[KnowledgeBaseResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeBaseResponse:
    """获取单个知识库。"""
    row = await kb_service.get_knowledge_base(db, kb_id, org_id=org_id)
    return KnowledgeBaseResponse.model_validate(row)


@router.put(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    data: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeBaseResponse:
    """更新知识库。"""
    row = await kb_service.update_knowledge_base(db, kb_id, data, org_id=org_id)
    return KnowledgeBaseResponse.model_validate(row)


@router.delete(
    "/{kb_id}",
    status_code=204,
    dependencies=[Depends(require_permission("memories", "delete"))],
)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> None:
    """删除知识库。"""
    await kb_service.delete_knowledge_base(db, kb_id, org_id=org_id)


@router.post(
    "/{kb_id}/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeDocumentResponse:
    """上传并索引文档。"""
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    row = await kb_service.ingest_document(
        db,
        kb_id,
        filename=file.filename or "unknown.txt",
        media_type=file.content_type or "text/plain",
        content=text,
        size_bytes=len(raw),
        org_id=org_id,
    )
    return KnowledgeDocumentResponse.model_validate(row)


@router.get(
    "/{kb_id}/documents",
    response_model=list[KnowledgeDocumentResponse],
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def list_documents(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> list[KnowledgeDocumentResponse]:
    """列出知识库文档。"""
    rows = await kb_service.list_documents(db, kb_id, org_id=org_id)
    return [KnowledgeDocumentResponse.model_validate(r) for r in rows]


@router.post(
    "/{kb_id}/search",
    response_model=KnowledgeSearchResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def search_knowledge_base(
    kb_id: uuid.UUID,
    data: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> KnowledgeSearchResponse:
    """检索知识库。"""
    items = await kb_service.search_knowledge_base(
        db,
        kb_id,
        query=data.query,
        top_k=data.top_k,
        min_score=data.min_score,
        org_id=org_id,
    )
    return KnowledgeSearchResponse(
        knowledge_base_id=kb_id,
        query=data.query,
        results=[KnowledgeSearchItem.model_validate(i) for i in items],
    )
