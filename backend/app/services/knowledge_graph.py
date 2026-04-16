"""知识图谱业务逻辑层。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models.knowledge_base import KnowledgeBaseRecord, KnowledgeChunkRecord
from app.models.knowledge_graph import (
    KnowledgeCommunityRecord,
    KnowledgeEntityRecord,
    KnowledgeRelationRecord,
)
from ckyclaw_framework.rag.graph.entity import (
    Entity,
    Relation,
)
from ckyclaw_framework.rag.graph.extractor import LLMGraphExtractor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.schemas.knowledge_graph import BuildGraphRequest

logger = logging.getLogger(__name__)

# Redis key 前缀
_GRAPH_BUILD_PREFIX = "graph:build:"
_GRAPH_EXTRACT_PREFIX = "graph:extract:"


async def build_graph(
    db: AsyncSession,
    redis: Any,
    kb_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    provider_kwargs: dict[str, Any],
    data: BuildGraphRequest,
    *,
    org_id: uuid.UUID | None = None,
) -> dict[str, str]:
    """触发图谱构建（异步任务）。"""
    kb = await _get_kb(db, kb_id, org_id=org_id)
    if kb.mode not in ("graph", "hybrid"):
        msg = f"知识库 '{kb_id}' mode='{kb.mode}'，不支持图谱构建"
        raise ValueError(msg)

    task_id = uuid.uuid4().hex[:12]

    # 初始化 Redis 任务状态
    task_key = f"{_GRAPH_BUILD_PREFIX}{task_id}"
    await redis.set(
        task_key,
        json.dumps({
            "status": "pending",
            "progress": 0.0,
            "entity_count": 0,
            "relation_count": 0,
            "community_count": 0,
            "error": None,
        }),
        ex=86400 * 7,  # TTL 7 天
    )

    # 启动后台任务
    asyncio.create_task(
        _build_graph_task(
            session_factory=session_factory,
            redis=redis,
            kb_id=kb_id,
            provider_kwargs=provider_kwargs,
            data=data,
            task_id=task_id,
        )
    )

    return {"task_id": task_id, "status": "started"}


async def _build_graph_task(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Any,
    kb_id: uuid.UUID,
    provider_kwargs: dict[str, Any],
    data: BuildGraphRequest,
    task_id: str,
) -> None:
    """后台图谱构建任务。"""
    task_key = f"{_GRAPH_BUILD_PREFIX}{task_id}"

    try:
        await _update_task_status(redis, task_key, status="processing", progress=0.0)

        async with session_factory() as db:
            # 1. 加载文档 chunks
            stmt = (
                select(KnowledgeChunkRecord)
                .where(
                    KnowledgeChunkRecord.knowledge_base_id == kb_id,
                    KnowledgeChunkRecord.is_deleted == False,  # noqa: E712
                )
                .order_by(KnowledgeChunkRecord.document_id, KnowledgeChunkRecord.chunk_index)
            )
            chunks = (await db.execute(stmt)).scalars().all()

            if not chunks:
                await _update_task_status(redis, task_key, status="completed", progress=1.0)
                return

            total_chunks = len(chunks)

            # 2. 构造 LLM Provider
            from ckyclaw_framework.model.litellm_provider import LiteLLMProvider

            model_provider = LiteLLMProvider(**provider_kwargs)
            extractor = LLMGraphExtractor()

            # 3. 逐 chunk 抽取
            all_entities: list[Entity] = []
            all_relations: list[Relation] = []

            for i, chunk in enumerate(chunks):
                content = chunk.content
                if not content.strip():
                    continue

                # 增量缓存检查
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                cache_key = f"{_GRAPH_EXTRACT_PREFIX}{content_hash}"
                cached = await redis.get(cache_key)
                if cached:
                    try:
                        cached_data = json.loads(cached)
                        for e_data in cached_data.get("entities", []):
                            all_entities.append(Entity(**e_data))
                        for r_data in cached_data.get("relations", []):
                            all_relations.append(Relation(**r_data))
                    except (json.JSONDecodeError, TypeError):
                        pass
                else:
                    # 调用 LLM 抽取
                    try:
                        result = await extractor.extract(
                            content,
                            chunk_index=chunk.chunk_index,
                            document_id=str(chunk.document_id),
                            entity_types=data.entity_types or None,
                            model_provider=model_provider,
                            model=data.extract_model,
                        )
                        all_entities.extend(result.entities)
                        all_relations.extend(result.relations)

                        # 缓存抽取结果（简化版：仅缓存 entity/relation 的基础字段）
                        cache_data = {
                            "entities": [
                                {
                                    "name": e.name,
                                    "entity_type": e.entity_type,
                                    "description": e.description,
                                    "confidence": e.confidence,
                                    "confidence_label": e.confidence_label.value,
                                    "attributes": e.attributes,
                                    "source_chunk": e.source_chunk,
                                    "document_id": e.document_id,
                                }
                                for e in result.entities
                            ],
                            "relations": [
                                {
                                    "source_name": r.source_name,
                                    "target_name": r.target_name,
                                    "relation_type": r.relation_type,
                                    "description": r.description,
                                    "weight": r.weight,
                                    "confidence": r.confidence,
                                    "confidence_label": r.confidence_label.value,
                                    "source_chunk": r.source_chunk,
                                }
                                for r in result.relations
                            ],
                        }
                        await redis.set(cache_key, json.dumps(cache_data), ex=86400 * 7)
                    except Exception as e:
                        logger.warning("Chunk %d 抽取失败: %s", i, e)

                # 更新进度
                progress = (i + 1) / total_chunks
                await _update_task_status(
                    redis, task_key, progress=progress, entity_count=len(all_entities)
                )

            # 4. 实体消歧合并 + 持久化
            entity_name_to_id = await _merge_and_persist_entities(db, kb_id, all_entities)

            # 5. 持久化关系
            relation_count = await _persist_relations(db, kb_id, all_relations, entity_name_to_id)

            # 6. 清除旧的社区数据，重新检测（Phase 3 实现完整社区检测）
            # 当前阶段先跳过社区检测，仅存储实体和关系

            await db.commit()

            await _update_task_status(
                redis,
                task_key,
                status="completed",
                progress=1.0,
                entity_count=len(entity_name_to_id),
                relation_count=relation_count,
            )

    except Exception as e:
        logger.exception("图谱构建任务 %s 失败", task_id)
        await _update_task_status(redis, task_key, status="failed", error=str(e))


async def _merge_and_persist_entities(
    db: AsyncSession,
    kb_id: uuid.UUID,
    entities: list[Entity],
) -> dict[str, uuid.UUID]:
    """消歧合并实体并持久化到 PG。返回 name -> id 映射。"""
    # 按 (name, entity_type) 分组
    from collections import defaultdict

    groups: dict[tuple[str, str], list[Entity]] = defaultdict(list)
    for entity in entities:
        groups[(entity.name, entity.entity_type)].append(entity)

    name_to_id: dict[str, uuid.UUID] = {}

    for (name, entity_type), group in groups.items():
        # 合并同组实体
        merged = group[0]
        for extra in group[1:]:
            merged = _merge_two_entities(merged, extra)

        # 查找是否已有同名同类型实体
        stmt = select(KnowledgeEntityRecord).where(
            KnowledgeEntityRecord.knowledge_base_id == kb_id,
            KnowledgeEntityRecord.name == name,
            KnowledgeEntityRecord.entity_type == entity_type,
            KnowledgeEntityRecord.is_deleted == False,  # noqa: E712
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # 合并到已有记录
            existing.description = (
                merged.description if len(merged.description) > len(existing.description) else existing.description
            )
            existing.attributes = {**existing.attributes, **merged.attributes}
            existing.confidence = max(existing.confidence, merged.confidence)
            existing.confidence_label = merged.confidence_label.value
            name_to_id[name] = existing.id
        else:
            # 新建
            doc_id = uuid.UUID(merged.document_id) if merged.document_id else uuid.uuid4()
            record = KnowledgeEntityRecord(
                knowledge_base_id=kb_id,
                document_id=doc_id,
                name=name,
                entity_type=entity_type,
                description=merged.description,
                attributes=merged.attributes,
                source_chunks={"chunks": [merged.source_chunk]} if merged.source_chunk else {},
                confidence=merged.confidence,
                confidence_label=merged.confidence_label.value,
                content_hash=hashlib.sha256(merged.source_chunk.encode()).hexdigest() if merged.source_chunk else "",
            )
            db.add(record)
            await db.flush()
            name_to_id[name] = record.id

    return name_to_id


async def _persist_relations(
    db: AsyncSession,
    kb_id: uuid.UUID,
    relations: list[Relation],
    name_to_id: dict[str, uuid.UUID],
) -> int:
    """持久化关系到 PG。返回写入数量。"""
    count = 0
    for rel in relations:
        source_id = name_to_id.get(rel.source_name)
        target_id = name_to_id.get(rel.target_name)
        if not source_id or not target_id:
            continue

        record = KnowledgeRelationRecord(
            knowledge_base_id=kb_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=rel.relation_type,
            description=rel.description,
            weight=rel.weight,
            source_chunk=rel.source_chunk,
            confidence=rel.confidence,
            confidence_label=rel.confidence_label.value,
        )
        db.add(record)
        count += 1

    return count


async def get_graph_build_status(redis: Any, task_id: str) -> dict[str, Any]:
    """查询图谱构建进度。"""
    task_key = f"{_GRAPH_BUILD_PREFIX}{task_id}"
    raw = await redis.get(task_key)
    if not raw:
        msg = f"任务 '{task_id}' 不存在或已过期"
        raise NotFoundError(msg)
    return json.loads(raw)


async def list_entities(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    name_contains: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[KnowledgeEntityRecord], int]:
    """查询实体列表。"""
    await _ensure_kb(db, kb_id)
    base = select(KnowledgeEntityRecord).where(
        KnowledgeEntityRecord.knowledge_base_id == kb_id,
        KnowledgeEntityRecord.is_deleted == False,  # noqa: E712
    )
    if name_contains:
        base = base.where(KnowledgeEntityRecord.name.ilike(f"%{name_contains}%"))
    if entity_type:
        base = base.where(KnowledgeEntityRecord.entity_type == entity_type)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(KnowledgeEntityRecord.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def get_entity(db: AsyncSession, entity_id: uuid.UUID) -> KnowledgeEntityRecord:
    """获取单个实体。"""
    stmt = select(KnowledgeEntityRecord).where(
        KnowledgeEntityRecord.id == entity_id,
        KnowledgeEntityRecord.is_deleted == False,  # noqa: E712
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        msg = f"实体 '{entity_id}' 不存在"
        raise NotFoundError(msg)
    return row


async def list_relations(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    relation_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[KnowledgeRelationRecord], int]:
    """查询关系列表。"""
    await _ensure_kb(db, kb_id)
    base = select(KnowledgeRelationRecord).where(
        KnowledgeRelationRecord.knowledge_base_id == kb_id,
        KnowledgeRelationRecord.is_deleted == False,  # noqa: E712
    )
    if relation_type:
        base = base.where(KnowledgeRelationRecord.relation_type == relation_type)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(KnowledgeRelationRecord.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def list_communities(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    level: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[KnowledgeCommunityRecord], int]:
    """查询社区列表。"""
    await _ensure_kb(db, kb_id)
    base = select(KnowledgeCommunityRecord).where(
        KnowledgeCommunityRecord.knowledge_base_id == kb_id,
        KnowledgeCommunityRecord.is_deleted == False,  # noqa: E712
    )
    if level is not None:
        base = base.where(KnowledgeCommunityRecord.level == level)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(KnowledgeCommunityRecord.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def get_graph_data(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    max_nodes: int = 200,
) -> dict[str, Any]:
    """获取图谱可视化数据。"""
    await _ensure_kb(db, kb_id)

    # 加载实体
    entity_stmt = (
        select(KnowledgeEntityRecord)
        .where(
            KnowledgeEntityRecord.knowledge_base_id == kb_id,
            KnowledgeEntityRecord.is_deleted == False,  # noqa: E712
        )
        .order_by(KnowledgeEntityRecord.confidence.desc())
        .limit(max_nodes)
    )
    entities = (await db.execute(entity_stmt)).scalars().all()

    entity_ids = {e.id for e in entities}

    # 加载关系（仅包含两端都在实体列表中的）
    rel_stmt = select(KnowledgeRelationRecord).where(
        KnowledgeRelationRecord.knowledge_base_id == kb_id,
        KnowledgeRelationRecord.source_entity_id.in_(entity_ids),
        KnowledgeRelationRecord.target_entity_id.in_(entity_ids),
        KnowledgeRelationRecord.is_deleted == False,  # noqa: E712
    )
    relations = (await db.execute(rel_stmt)).scalars().all()

    nodes = [
        {"id": str(e.id), "label": e.name, "type": e.entity_type, "confidence": e.confidence}
        for e in entities
    ]
    edges = [
        {
            "source": str(r.source_entity_id),
            "target": str(r.target_entity_id),
            "type": r.relation_type,
            "weight": r.weight,
        }
        for r in relations
    ]

    return {"nodes": nodes, "edges": edges}


async def delete_graph(db: AsyncSession, kb_id: uuid.UUID) -> dict[str, int]:
    """清空知识库的图谱数据。"""
    now = datetime.now(UTC)

    # 软删除所有实体、关系、社区
    for model in (KnowledgeRelationRecord, KnowledgeEntityRecord, KnowledgeCommunityRecord):
        stmt = (
            select(model)
            .where(model.knowledge_base_id == kb_id, model.is_deleted == False)  # noqa: E712
        )
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            row.is_deleted = True
            row.deleted_at = now

    entity_count = len([r for r in rows if isinstance(r, KnowledgeEntityRecord)])
    await db.commit()

    return {"deleted_count": entity_count}


async def graph_search(
    db: AsyncSession,
    kb_id: uuid.UUID,
    *,
    query: str,
    top_k: int = 10,
    max_depth: int = 2,
    search_mode: str = "hybrid",
    provider_kwargs: dict[str, Any] | None = None,
    extract_model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """图谱检索。基于 PG 数据直接检索（不依赖 GraphStore 接口）。

    返回简化的结果列表，每项包含 entity/relation/community + score + source。
    """
    await _ensure_kb(db, kb_id)

    results: list[dict[str, Any]] = []

    # 路径 1: 实体模糊匹配
    if search_mode in ("entity", "hybrid"):
        # 提取关键词（简单分词 + 长词优先）
        keywords = [w for w in query.replace("?", "").replace("？", "").replace("的", " ").split() if len(w) > 1]
        for kw in keywords[:5]:
            stmt = select(KnowledgeEntityRecord).where(
                KnowledgeEntityRecord.knowledge_base_id == kb_id,
                KnowledgeEntityRecord.name.ilike(f"%{kw}%"),
                KnowledgeEntityRecord.is_deleted == False,  # noqa: E712
            ).limit(5)
            rows = (await db.execute(stmt)).scalars().all()
            for row in rows:
                results.append({
                    "entity": {
                        "id": str(row.id),
                        "name": row.name,
                        "entity_type": row.entity_type,
                        "description": row.description,
                        "confidence": row.confidence,
                        "confidence_label": row.confidence_label,
                    },
                    "score": 0.9 if row.name.lower() == kw.lower() else 0.7,
                    "source": "entity_match",
                })

    # 路径 2: 关系遍历（基于匹配到的实体 ID，1跳）
    if search_mode in ("traverse", "hybrid") and results:
        entity_ids = {
            uuid.UUID(r["entity"]["id"])
            for r in results
            if r.get("entity") and r["source"] == "entity_match"
        }
        for eid in list(entity_ids)[:3]:
            rel_stmt = select(KnowledgeRelationRecord).where(
                KnowledgeRelationRecord.knowledge_base_id == kb_id,
                (KnowledgeRelationRecord.source_entity_id == eid) | (KnowledgeRelationRecord.target_entity_id == eid),
                KnowledgeRelationRecord.is_deleted == False,  # noqa: E712
            ).limit(10)
            rels = (await db.execute(rel_stmt)).scalars().all()
            for rel in rels:
                # 获取另一端的实体
                other_id = rel.target_entity_id if rel.source_entity_id == eid else rel.source_entity_id
                other = (await db.execute(
                    select(KnowledgeEntityRecord).where(KnowledgeEntityRecord.id == other_id)
                )).scalar_one_or_none()
                if other:
                    results.append({
                        "entity": {
                            "id": str(other.id),
                            "name": other.name,
                            "entity_type": other.entity_type,
                            "description": other.description,
                        },
                        "relation": {
                            "id": str(rel.id),
                            "source_entity_id": str(rel.source_entity_id),
                            "target_entity_id": str(rel.target_entity_id),
                            "relation_type": rel.relation_type,
                            "description": rel.description,
                            "weight": rel.weight,
                        },
                        "score": 0.6,
                        "source": "relation_traverse",
                    })

    # 路径 3: 社区摘要
    if search_mode in ("community", "hybrid") and results:
        entity_names = {
            r["entity"]["name"] for r in results if r.get("entity")
        }
        comm_stmt = select(KnowledgeCommunityRecord).where(
            KnowledgeCommunityRecord.knowledge_base_id == kb_id,
            KnowledgeCommunityRecord.is_deleted == False,  # noqa: E712
        ).limit(50)
        communities = (await db.execute(comm_stmt)).scalars().all()
        seen_communities: set[str] = set()
        for comm in communities:
            if not comm.entity_ids:
                continue
            # 检查社区内是否有匹配实体
            comm_names: set[str] = set()
            for eid in comm.entity_ids:
                entity = (await db.execute(
                    select(KnowledgeEntityRecord).where(KnowledgeEntityRecord.id == eid)
                )).scalar_one_or_none()
                if entity:
                    comm_names.add(entity.name)
            if comm_names & entity_names and str(comm.id) not in seen_communities:
                seen_communities.add(str(comm.id))
                results.append({
                    "community": {
                        "id": str(comm.id),
                        "name": comm.name,
                        "summary": comm.summary,
                        "level": comm.level,
                    },
                    "score": 0.75,
                    "source": "community_summary",
                })

    # 去重 + 排序 + 截断
    seen_keys: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in results:
        key = r["source"]
        if r.get("entity"):
            key += f":e:{r['entity'].get('name', '')}"
        elif r.get("community"):
            key += f":c:{r['community'].get('name', '')}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(r)

    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique[:top_k]


# --- Helpers ---


async def _get_kb(db: AsyncSession, kb_id: uuid.UUID, *, org_id: uuid.UUID | None = None) -> KnowledgeBaseRecord:
    """获取知识库（带 org 隔离）。"""
    stmt = select(KnowledgeBaseRecord).where(
        KnowledgeBaseRecord.id == kb_id,
        KnowledgeBaseRecord.is_deleted == False,  # noqa: E712
    )
    if org_id is not None:
        stmt = stmt.where(KnowledgeBaseRecord.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        msg = f"知识库 '{kb_id}' 不存在"
        raise NotFoundError(msg)
    return row


async def _ensure_kb(db: AsyncSession, kb_id: uuid.UUID) -> None:
    """确保知识库存在。"""
    await _get_kb(db, kb_id)


async def _update_task_status(
    redis: Any,
    task_key: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    entity_count: int | None = None,
    relation_count: int | None = None,
    community_count: int | None = None,
    error: str | None = None,
) -> None:
    """更新 Redis 中的任务状态。"""
    raw = await redis.get(task_key)
    current = json.loads(raw) if raw else {}
    if status is not None:
        current["status"] = status
    if progress is not None:
        current["progress"] = progress
    if entity_count is not None:
        current["entity_count"] = entity_count
    if relation_count is not None:
        current["relation_count"] = relation_count
    if community_count is not None:
        current["community_count"] = community_count
    if error is not None:
        current["error"] = error
    await redis.set(task_key, json.dumps(current), ex=86400 * 7)


def _merge_two_entities(a: Entity, b: Entity) -> Entity:
    """合并两个同名同类型实体。"""
    merged_attrs = {**a.attributes, **b.attributes}
    merged_confidence = max(a.confidence, b.confidence)
    merged_desc = a.description if len(a.description) >= len(b.description) else b.description
    chunks: list[str] = []
    if a.source_chunk:
        chunks.append(a.source_chunk)
    if b.source_chunk:
        chunks.append(b.source_chunk)
    return Entity(
        name=a.name,
        entity_type=a.entity_type,
        description=merged_desc,
        attributes=merged_attrs,
        source_chunk="\n---\n".join(chunks) if chunks else "",
        confidence=merged_confidence,
        confidence_label=a.confidence_label,
        document_id=a.document_id or b.document_id,
    )
