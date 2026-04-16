"""知识图谱 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import get_org_id
from app.schemas.knowledge_graph import (
    BuildGraphRequest,
    CommunityListResponse,
    CommunityResponse,
    EntityListResponse,
    EntityResponse,
    GraphBuildStatusResponse,
    GraphDataResponse,
    GraphSearchRequest,
    GraphSearchResponse,
    RelationListResponse,
    RelationResponse,
)
from app.services import knowledge_graph as kg_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-graph"])


@router.post(
    "/{kb_id}/build-graph",
    status_code=202,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def build_graph(
    kb_id: uuid.UUID,
    data: BuildGraphRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> dict[str, str]:
    """触发图谱构建（异步任务）。"""
    from app.core.database import async_session_factory
    from app.core.redis import get_redis

    redis = await get_redis()

    # TODO: 从 ProviderConfig 解析 provider_kwargs（复用 session.py 的 _resolve_provider_kwargs）
    provider_kwargs: dict[str, str] = {}

    return await kg_service.build_graph(
        db,
        redis,
        kb_id,
        async_session_factory,
        provider_kwargs,
        data,
        org_id=org_id,
    )


@router.get(
    "/{kb_id}/graph-status",
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def get_graph_build_status(
    kb_id: uuid.UUID,
    task_id: str = Query(..., description="构建任务 ID"),
) -> GraphBuildStatusResponse:
    """查询图谱构建进度。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    status = await kg_service.get_graph_build_status(redis, task_id)
    return GraphBuildStatusResponse(task_id=task_id, **status)


@router.get(
    "/{kb_id}/entities",
    response_model=EntityListResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def list_entities(
    kb_id: uuid.UUID,
    name_contains: str | None = Query(None, description="实体名称过滤"),
    entity_type: str | None = Query(None, description="实体类型过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> EntityListResponse:
    """查询实体列表。"""
    rows, total = await kg_service.list_entities(
        db, kb_id, name_contains=name_contains, entity_type=entity_type, limit=limit, offset=offset
    )
    return EntityListResponse(
        data=[EntityResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{kb_id}/entities/{entity_id}",
    response_model=EntityResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def get_entity(
    kb_id: uuid.UUID,
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EntityResponse:
    """获取单个实体。"""
    row = await kg_service.get_entity(db, entity_id)
    return EntityResponse.model_validate(row)


@router.get(
    "/{kb_id}/relations",
    response_model=RelationListResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def list_relations(
    kb_id: uuid.UUID,
    relation_type: str | None = Query(None, description="关系类型过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RelationListResponse:
    """查询关系列表。"""
    rows, total = await kg_service.list_relations(
        db, kb_id, relation_type=relation_type, limit=limit, offset=offset
    )
    return RelationListResponse(
        data=[RelationResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{kb_id}/communities",
    response_model=CommunityListResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def list_communities(
    kb_id: uuid.UUID,
    level: int | None = Query(None, description="社区层级过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CommunityListResponse:
    """查询社区列表。"""
    rows, total = await kg_service.list_communities(
        db, kb_id, level=level, limit=limit, offset=offset
    )
    return CommunityListResponse(
        data=[
            CommunityResponse(
                id=r.id,
                knowledge_base_id=r.knowledge_base_id,
                name=r.name,
                summary=r.summary,
                entity_count=len(r.entity_ids) if r.entity_ids else 0,
                level=r.level,
                parent_community_id=r.parent_community_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{kb_id}/graph",
    response_model=GraphDataResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def get_graph_data(
    kb_id: uuid.UUID,
    max_nodes: int = Query(200, ge=10, le=2000),
    db: AsyncSession = Depends(get_db),
) -> GraphDataResponse:
    """获取图谱可视化数据。"""
    data = await kg_service.get_graph_data(db, kb_id, max_nodes=max_nodes)
    return GraphDataResponse(**data)


@router.delete(
    "/{kb_id}/graph",
    status_code=200,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def delete_graph(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """清空图谱数据。"""
    return await kg_service.delete_graph(db, kb_id)


@router.post(
    "/{kb_id}/graph-search",
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def graph_search(
    kb_id: uuid.UUID,
    data: GraphSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> GraphSearchResponse:
    """图谱检索。"""
    results = await kg_service.graph_search(
        db,
        kb_id,
        query=data.query,
        top_k=data.top_k,
        max_depth=data.max_depth,
        search_mode=data.search_mode,
    )
    return GraphSearchResponse(
        knowledge_base_id=kb_id,
        query=data.query,
        results=results,
    )
