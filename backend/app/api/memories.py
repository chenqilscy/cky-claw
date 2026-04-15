"""Memory 记忆管理 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import check_quota, get_org_id
from app.schemas.memory import (
    MemoryCountResponse,
    MemoryCreate,
    MemoryDecayRequest,
    MemoryDecayResponse,
    MemoryListResponse,
    MemoryResponse,
    MemorySearchRequest,
    MemoryTagSearchRequest,
    MemoryUpdate,
)
from app.services import memory as memory_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=201,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def create_memory(
    data: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> MemoryResponse:
    """创建记忆条目。"""
    await check_quota(db, org_id, "max_memories")
    record = await memory_service.create_memory(db, data)
    return MemoryResponse.model_validate(record)


@router.get("", response_model=MemoryListResponse, dependencies=[Depends(require_permission("memories", "read"))])
async def list_memories(
    user_id: str | None = Query(None, description="按用户筛选"),
    type: str | None = Query(None, alias="type", description="按类型筛选"),
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> MemoryListResponse:
    """查询记忆列表。"""
    rows, total = await memory_service.list_memories(
        db,
        user_id=user_id,
        memory_type=type,
        agent_name=agent_name,
        limit=limit,
        offset=offset,
        org_id=org_id,
    )
    return MemoryListResponse(
        data=[MemoryResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{entry_id}",
    response_model=MemoryResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def get_memory(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """获取单条记忆。"""
    record = await memory_service.get_memory(db, entry_id)
    return MemoryResponse.model_validate(record)


@router.put(
    "/{entry_id}",
    response_model=MemoryResponse,
    dependencies=[Depends(require_permission("memories", "write"))],
)
async def update_memory(
    entry_id: uuid.UUID,
    data: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """更新记忆条目。"""
    record = await memory_service.update_memory(db, entry_id, data)
    return MemoryResponse.model_validate(record)


@router.delete(
    "/user/{user_id}",
    dependencies=[Depends(require_permission("memories", "delete"))],
)
async def delete_user_memories(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """删除指定用户的全部记忆（GDPR 合规）。"""
    count = await memory_service.delete_user_memories(db, user_id)
    return {"deleted": count}


@router.delete(
    "/{entry_id}",
    status_code=204,
    dependencies=[Depends(require_permission("memories", "delete"))],
)
async def delete_memory(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除记忆条目。"""
    await memory_service.delete_memory(db, entry_id)


@router.post(
    "/search",
    response_model=list[MemoryResponse],
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def search_memories(
    data: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[MemoryResponse]:
    """搜索记忆条目。"""
    rows = await memory_service.search_memories(db, data)
    return [MemoryResponse.model_validate(r) for r in rows]


@router.post(
    "/search-by-tags",
    response_model=list[MemoryResponse],
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def search_by_tags(
    data: MemoryTagSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[MemoryResponse]:
    """按标签搜索记忆条目（OR 匹配）。"""
    rows = await memory_service.search_by_tags(db, data)
    return [MemoryResponse.model_validate(r) for r in rows]


@router.get(
    "/count/{user_id}",
    response_model=MemoryCountResponse,
    dependencies=[Depends(require_permission("memories", "read"))],
)
async def count_memories(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> MemoryCountResponse:
    """获取用户记忆条目总数。"""
    count = await memory_service.count_memories(db, user_id)
    return MemoryCountResponse(user_id=user_id, count=count)


@router.post(
    "/decay",
    response_model=MemoryDecayResponse,
    dependencies=[Depends(require_permission("memories", "execute"))],
)
async def decay_memories(
    data: MemoryDecayRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryDecayResponse:
    """触发置信度衰减。"""
    affected = await memory_service.decay_memories(db, data)
    return MemoryDecayResponse(affected=affected)
