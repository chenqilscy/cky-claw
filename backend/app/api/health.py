"""健康检查路由。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok", "service": "ckyclaw-backend"}
