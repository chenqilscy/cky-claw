"""APM 仪表盘 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.apm import ApmDashboardResponse
from app.services import apm as apm_service

router = APIRouter(prefix="/api/v1/apm", tags=["apm"])


@router.get("/dashboard", response_model=ApmDashboardResponse)
async def get_apm_dashboard(
    days: int = Query(30, ge=1, le=365, description="统计范围（天）"),
    db: AsyncSession = Depends(get_db),
) -> ApmDashboardResponse:
    """获取 APM 仪表盘聚合数据。"""
    return await apm_service.get_apm_dashboard(db, days=days)
