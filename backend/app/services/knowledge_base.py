"""知识库业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ckyclaw_framework.rag.chunker import FixedSizeChunker
from ckyclaw_framework.rag.document import Document
from ckyclaw_framework.rag.embedding import InMemoryEmbeddingProvider
from ckyclaw_framework.rag.vector_store import cosine_similarity

from app.core.exceptions import NotFoundError
from app.models.knowledge_base import (
    KnowledgeBaseRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
)
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


async def create_knowledge_base(
    db: AsyncSession,
    data: KnowledgeBaseCreate,
    *,
    org_id: uuid.UUID | None = None,
) -> KnowledgeBaseRecord:
    """创建知识库。"""
    record = KnowledgeBaseRecord(
        name=data.name,
        description=data.description,
        embedding_model=data.embedding_model,
        chunk_strategy=data.chunk_strategy,
        metadata_=data.metadata,
        org_id=org_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_knowledge_base(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> KnowledgeBaseRecord:
    """获取知识库。"""
    stmt = select(KnowledgeBaseRecord).where(
        KnowledgeBaseRecord.id == kb_id,
        KnowledgeBaseRecord.is_deleted == False,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where(KnowledgeBaseRecord.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"知识库 '{kb_id}' 不存在")
    return row


async def list_knowledge_bases(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[KnowledgeBaseRecord], int]:
    """分页查询知识库。"""
    base = select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(KnowledgeBaseRecord.org_id == org_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(KnowledgeBaseRecord.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def update_knowledge_base(
    db: AsyncSession,
    kb_id: uuid.UUID,
    data: KnowledgeBaseUpdate,
    *,
    org_id: uuid.UUID | None = None,
) -> KnowledgeBaseRecord:
    """更新知识库。"""
    row = await get_knowledge_base(db, kb_id, org_id=org_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "metadata":
            row.metadata_ = value
        else:
            setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_knowledge_base(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> None:
    """软删除知识库。"""
    row = await get_knowledge_base(db, kb_id, org_id=org_id)
    now = datetime.now(timezone.utc)
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    await db.commit()


async def list_documents(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> list[KnowledgeDocumentRecord]:
    """列出知识库下文档。"""
    await get_knowledge_base(db, kb_id, org_id=org_id)
    stmt = (
        select(KnowledgeDocumentRecord)
        .where(
            KnowledgeDocumentRecord.knowledge_base_id == kb_id,
            KnowledgeDocumentRecord.is_deleted == False,  # noqa: E712
        )
        .order_by(KnowledgeDocumentRecord.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def ingest_document(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    filename: str,
    media_type: str,
    content: str,
    size_bytes: int,
    org_id: uuid.UUID | None = None,
) -> KnowledgeDocumentRecord:
    """将文档分块、向量化并写入数据库。"""
    kb = await get_knowledge_base(db, kb_id, org_id=org_id)

    document = KnowledgeDocumentRecord(
        knowledge_base_id=kb.id,
        filename=filename,
        media_type=media_type,
        size_bytes=size_bytes,
        status="processing",
        metadata_={},
    )
    db.add(document)
    await db.flush()

    strategy = kb.chunk_strategy or {}
    chunk_size = int(strategy.get("chunk_size", 512))
    overlap = int(strategy.get("overlap", 64))
    chunker = FixedSizeChunker(chunk_size=chunk_size, overlap=overlap)

    chunks = chunker.split(Document(content=content, metadata={"source": filename}))
    embedder = InMemoryEmbeddingProvider(dimension=128)
    embeddings = await embedder.embed([c.content for c in chunks]) if chunks else []

    for index, chunk in enumerate(chunks):
        record = KnowledgeChunkRecord(
            knowledge_base_id=kb.id,
            document_id=document.id,
            chunk_index=index,
            content=chunk.content,
            embedding=embeddings[index],
            metadata_=chunk.metadata,
        )
        db.add(record)

    document.status = "indexed"
    document.chunk_count = len(chunks)
    document.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(document)
    return document


async def search_knowledge_base(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """在知识库中执行向量检索。"""
    await get_knowledge_base(db, kb_id, org_id=org_id)

    stmt = select(KnowledgeChunkRecord).where(
        KnowledgeChunkRecord.knowledge_base_id == kb_id,
        KnowledgeChunkRecord.is_deleted == False,  # noqa: E712
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return []

    embedder = InMemoryEmbeddingProvider(dimension=128)
    query_embedding = await embedder.embed_single(query)

    scored: list[tuple[float, KnowledgeChunkRecord]] = []
    for row in rows:
        if row.embedding is None:
            continue
        score = cosine_similarity(query_embedding, row.embedding)
        if score >= min_score:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "chunk_id": row.id,
            "document_id": row.document_id,
            "content": row.content,
            "score": score,
            "metadata": row.metadata_ or {},
        }
        for score, row in scored[:top_k]
    ]
