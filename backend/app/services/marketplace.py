"""Marketplace 业务逻辑层。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.agent_template import AgentTemplate, MarketplaceReview


async def list_marketplace(
    db: AsyncSession,
    *,
    category: str | None = None,
    search: str | None = None,
    sort_by: str = "downloads",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AgentTemplate], int]:
    """查询已发布的市场模板列表。"""
    base = select(AgentTemplate).where(
        AgentTemplate.published == True,  # noqa: E712
        AgentTemplate.is_deleted == False,  # noqa: E712
    )
    if category:
        base = base.where(AgentTemplate.category == category)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            AgentTemplate.display_name.ilike(pattern)
            | AgentTemplate.description.ilike(pattern)
        )

    # 计算总数
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # 排序
    order_map = {
        "downloads": AgentTemplate.downloads.desc(),
        "rating": AgentTemplate.rating.desc(),
        "newest": AgentTemplate.created_at.desc(),
    }
    order = order_map.get(sort_by, AgentTemplate.downloads.desc())
    rows = (
        await db.execute(base.order_by(order).offset(offset).limit(limit))
    ).scalars().all()
    return list(rows), total


async def publish_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    author_org_id: uuid.UUID | None = None,
) -> AgentTemplate:
    """发布模板到市场。"""
    tpl = await _get_template(db, template_id)
    if tpl.published:
        raise ConflictError("模板已发布")
    tpl.published = True
    if author_org_id:
        tpl.author_org_id = author_org_id
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def unpublish_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> AgentTemplate:
    """从市场下架模板。"""
    tpl = await _get_template(db, template_id)
    if not tpl.published:
        raise ConflictError("模板未发布")
    tpl.published = False
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def install_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> dict[str, object]:
    """从市场安装模板——递增下载次数并返回配置。"""
    tpl = await _get_template(db, template_id)
    if not tpl.published:
        raise ValidationError("模板未发布，无法安装")
    # 原子递增下载次数
    await db.execute(
        update(AgentTemplate)
        .where(AgentTemplate.id == template_id)
        .values(downloads=AgentTemplate.downloads + 1)
    )
    await db.commit()
    await db.refresh(tpl)
    return dict(tpl.config) if tpl.config else {}


async def create_review(
    db: AsyncSession,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    score: int,
    comment: str = "",
) -> MarketplaceReview:
    """用户评价模板（每用户每模板仅一次）。"""
    tpl = await _get_template(db, template_id)
    if not tpl.published:
        raise ValidationError("模板未发布，无法评价")

    # 检查是否已评价
    existing = await db.execute(
        select(MarketplaceReview).where(
            MarketplaceReview.template_id == template_id,
            MarketplaceReview.user_id == user_id,
            MarketplaceReview.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("已评价过该模板")

    review = MarketplaceReview(
        template_id=template_id,
        user_id=user_id,
        score=score,
        comment=comment,
    )
    db.add(review)
    await db.flush()

    # 更新模板评分
    await _recalc_rating(db, template_id)
    await db.commit()
    await db.refresh(review)
    return review


async def list_reviews(
    db: AsyncSession,
    template_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MarketplaceReview], int]:
    """查询模板的评价列表。"""
    base = select(MarketplaceReview).where(
        MarketplaceReview.template_id == template_id,
        MarketplaceReview.is_deleted == False,  # noqa: E712
    )
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    rows = (
        await db.execute(
            base.order_by(MarketplaceReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return list(rows), total


async def get_marketplace_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> AgentTemplate:
    """获取单个市场模板详情。"""
    tpl = await _get_template(db, template_id)
    if not tpl.published:
        raise NotFoundError("模板未发布或不存在")
    return tpl


# --- 内部辅助 ---

async def _get_template(db: AsyncSession, template_id: uuid.UUID) -> AgentTemplate:
    """获取模板（含未发布的）。"""
    stmt = select(AgentTemplate).where(
        AgentTemplate.id == template_id,
        AgentTemplate.is_deleted == False,  # noqa: E712
    )
    tpl = (await db.execute(stmt)).scalar_one_or_none()
    if tpl is None:
        raise NotFoundError("模板不存在")
    return tpl


async def _recalc_rating(db: AsyncSession, template_id: uuid.UUID) -> None:
    """重新计算模板平均评分。"""
    stmt = select(
        func.avg(MarketplaceReview.score),
        func.count(MarketplaceReview.id),
    ).where(
        MarketplaceReview.template_id == template_id,
        MarketplaceReview.is_deleted == False,  # noqa: E712
    )
    row = (await db.execute(stmt)).one()
    avg_score = float(row[0]) if row[0] else 0.0
    count = int(row[1])
    await db.execute(
        update(AgentTemplate)
        .where(AgentTemplate.id == template_id)
        .values(rating=round(avg_score, 2), rating_count=count)
    )
