"""Marketplace API 路由 — 模板市场浏览/发布/安装/评价。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.schemas.marketplace import (
    InstallTemplateRequest,
    MarketplaceListResponse,
    MarketplaceTemplateResponse,
    PublishTemplateRequest,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)
from app.services import marketplace as mp_svc

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


# ------------------------------------------------------------------
# 浏览
# ------------------------------------------------------------------

@router.get("", response_model=MarketplaceListResponse)
async def browse_marketplace(
    category: str | None = Query(None, description="按分类筛选"),
    search: str | None = Query(None, description="搜索关键词"),
    sort_by: str = Query("downloads", description="排序方式：downloads / rating / newest"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MarketplaceListResponse:
    """浏览市场模板列表（公开接口）。"""
    rows, total = await mp_svc.list_marketplace(
        db, category=category, search=search, sort_by=sort_by, limit=limit, offset=offset,
    )
    return MarketplaceListResponse(
        data=[MarketplaceTemplateResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{template_id}",
    response_model=MarketplaceTemplateResponse,
)
async def get_marketplace_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MarketplaceTemplateResponse:
    """获取市场模板详情。"""
    tpl = await mp_svc.get_marketplace_template(db, template_id)
    return MarketplaceTemplateResponse.model_validate(tpl)


# ------------------------------------------------------------------
# 发布 / 下架
# ------------------------------------------------------------------

@router.post(
    "/publish",
    response_model=MarketplaceTemplateResponse,
    dependencies=[Depends(require_permission("templates", "write"))],
)
async def publish_template(
    body: PublishTemplateRequest,
    db: AsyncSession = Depends(get_db),
) -> MarketplaceTemplateResponse:
    """发布模板到市场。"""
    tpl = await mp_svc.publish_template(db, body.template_id)
    return MarketplaceTemplateResponse.model_validate(tpl)


@router.post(
    "/unpublish",
    response_model=MarketplaceTemplateResponse,
    dependencies=[Depends(require_permission("templates", "write"))],
)
async def unpublish_template(
    body: PublishTemplateRequest,
    db: AsyncSession = Depends(get_db),
) -> MarketplaceTemplateResponse:
    """从市场下架模板。"""
    tpl = await mp_svc.unpublish_template(db, body.template_id)
    return MarketplaceTemplateResponse.model_validate(tpl)


# ------------------------------------------------------------------
# 安装
# ------------------------------------------------------------------

@router.post(
    "/{template_id}/install",
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def install_template(
    template_id: uuid.UUID,
    _body: InstallTemplateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """安装市场模板，返回 Agent 配置。"""
    config = await mp_svc.install_template(db, template_id)
    return {"config": config}


# ------------------------------------------------------------------
# 评价
# ------------------------------------------------------------------

@router.post(
    "/{template_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
    dependencies=[Depends(require_permission("templates", "write"))],
)
async def submit_review(
    template_id: uuid.UUID,
    body: ReviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """提交模板评价。"""
    review = await mp_svc.create_review(
        db, template_id=template_id, user_id=user.id, score=body.score, comment=body.comment,
    )
    return ReviewResponse.model_validate(review)


@router.get(
    "/{template_id}/reviews",
    response_model=ReviewListResponse,
)
async def list_reviews(
    template_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """查询模板评价列表。"""
    rows, total = await mp_svc.list_reviews(db, template_id, limit=limit, offset=offset)
    return ReviewListResponse(
        data=[ReviewResponse.model_validate(r) for r in rows],
        total=total,
    )
