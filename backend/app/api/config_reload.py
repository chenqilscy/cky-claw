"""配置热加载 API — 手动刷新配置缓存。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.cache import config_cache
from app.core.deps import require_admin

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.post("/reload", dependencies=[Depends(require_admin)])
async def reload_all() -> dict:
    """清除全部配置缓存。"""
    count = config_cache.clear()
    return {"message": "全部配置缓存已清除", "cleared": count}


@router.post("/reload/{entity_type}", dependencies=[Depends(require_admin)])
async def reload_entity_type(entity_type: str) -> dict:
    """清除指定类型的配置缓存。"""
    allowed = {"agents", "guardrails", "tool-groups", "providers", "sessions", "teams", "workflows"}
    if entity_type not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"entity_type 必须是 {allowed} 之一")
    count = config_cache.invalidate_prefix(f"ckyclaw:{entity_type}:")
    return {"message": f"{entity_type} 配置缓存已清除", "cleared": count}
