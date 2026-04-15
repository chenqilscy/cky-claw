"""配置热加载 API — 手动刷新配置缓存 + 配置变更审计 + 回滚。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.cache import config_cache
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.tenant import get_org_id
from app.schemas.config_change_log import (
    ConfigChangeLogListResponse,
    ConfigChangeLogResponse,
    RollbackPreviewResponse,
)
from app.services import config_change as change_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.post("/reload", dependencies=[Depends(require_admin)])
async def reload_all() -> dict[str, Any]:
    """清除全部配置缓存。"""
    count = config_cache.clear()
    return {"message": "全部配置缓存已清除", "cleared": count}


@router.post("/reload/{entity_type}", dependencies=[Depends(require_admin)])
async def reload_entity_type(entity_type: str) -> dict[str, Any]:
    """清除指定类型的配置缓存。"""
    allowed = {"agents", "guardrails", "tool-groups", "providers", "sessions", "teams", "workflows"}
    if entity_type not in allowed:
        raise HTTPException(status_code=400, detail=f"entity_type 必须是 {allowed} 之一")
    count = config_cache.invalidate_prefix(f"ckyclaw:{entity_type}:")
    return {"message": f"{entity_type} 配置缓存已清除", "cleared": count}


# ---------------------------------------------------------------------------
# ConfigChangeLog 审计端点
# ---------------------------------------------------------------------------


@router.get("/change-logs", response_model=ConfigChangeLogListResponse)
async def list_change_logs(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    config_key: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ConfigChangeLogListResponse:
    """查询配置变更历史。"""
    logs, total = await change_service.list_change_logs(
        db, entity_type=entity_type, entity_id=entity_id, config_key=config_key,
        limit=limit, offset=offset, org_id=org_id,
    )
    return ConfigChangeLogListResponse(
        data=[ConfigChangeLogResponse.model_validate(log) for log in logs],
        total=total,
    )


@router.get("/change-logs/{change_id}", response_model=ConfigChangeLogResponse)
async def get_change_log(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ConfigChangeLogResponse:
    """查询单条配置变更详情。"""
    log = await change_service.get_change_log(db, change_id, org_id=org_id)
    if log is None:
        raise HTTPException(status_code=404, detail="变更记录不存在")
    return ConfigChangeLogResponse.model_validate(log)


@router.post("/rollback/{change_id}", response_model=ConfigChangeLogResponse)
async def rollback_change(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(require_admin),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ConfigChangeLogResponse:
    """回滚指定配置变更。"""
    change = await change_service.get_change_log(db, change_id, org_id=org_id)
    if change is None:
        raise HTTPException(status_code=404, detail="变更记录不存在")
    rollback_log = await change_service.rollback_change(
        db, change, changed_by=getattr(user, "id", None), org_id=org_id,
    )
    return ConfigChangeLogResponse.model_validate(rollback_log)


@router.get("/preview-rollback/{change_id}", response_model=RollbackPreviewResponse)
async def preview_rollback(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> RollbackPreviewResponse:
    """预览回滚效果。"""
    change = await change_service.get_change_log(db, change_id, org_id=org_id)
    if change is None:
        raise HTTPException(status_code=404, detail="变更记录不存在")
    return RollbackPreviewResponse(
        change_id=change.id,
        config_key=change.config_key,
        entity_type=change.entity_type,
        entity_id=change.entity_id,
        current_value=change.new_value,
        rollback_to_value=change.old_value,
    )
