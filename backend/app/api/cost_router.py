"""成本路由 API — 任务复杂度分类与 Provider 推荐。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.provider import ProviderConfig

from ckyclaw_framework.model.cost_router import (
    CostRouter,
    ModelTier,
    ProviderCandidate,
    classify_complexity,
)

router = APIRouter(prefix="/api/v1/cost-router", tags=["cost-router"])


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    """复杂度分类请求。"""
    text: str = Field(..., min_length=1, max_length=10000, description="待分类的输入文本")


class ClassifyResponse(BaseModel):
    """复杂度分类响应。"""
    tier: str = Field(description="推荐的模型层级")
    text_length: int = Field(description="输入文本长度")


class RecommendResponse(BaseModel):
    """Provider 推荐响应。"""
    tier: str = Field(description="分类得到的模型层级")
    provider_name: str | None = Field(description="推荐的 Provider 名称")
    provider_tier: str | None = Field(description="推荐 Provider 的实际层级")


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.post(
    "/classify",
    response_model=ClassifyResponse,
    dependencies=[Depends(require_permission("providers", "read"))],
)
async def classify_text(body: ClassifyRequest) -> ClassifyResponse:
    """对输入文本进行复杂度分类。"""
    tier = classify_complexity(body.text)
    return ClassifyResponse(tier=tier.value, text_length=len(body.text))


@router.post(
    "/recommend",
    response_model=RecommendResponse,
    dependencies=[Depends(require_permission("providers", "read"))],
)
async def recommend_provider(
    body: ClassifyRequest,
    capability: list[str] | None = Query(None, description="要求的能力标签"),
    db: AsyncSession = Depends(get_db),
) -> RecommendResponse:
    """根据输入文本分类并推荐最优 Provider。"""
    # 1. 从 DB 加载启用的 Provider 作为候选
    stmt = select(ProviderConfig).where(
        ProviderConfig.is_enabled.is_(True),
        ProviderConfig.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    providers = list(result.scalars().all())

    candidates: list[ProviderCandidate] = []
    for p in providers:
        try:
            tier_enum = ModelTier(p.model_tier)
        except ValueError:
            # 跳过层级值非法的 Provider（数据兼容性保护）
            continue
        candidates.append(ProviderCandidate(
            name=p.name,
            model_tier=tier_enum,
            capabilities=p.capabilities or [],
            is_enabled=True,
        ))

    # 2. 创建路由器并推荐
    router_instance = CostRouter(candidates=candidates)
    tier = router_instance.classify(body.text)
    recommended = router_instance.recommend(body.text, required_capabilities=capability)

    return RecommendResponse(
        tier=tier.value,
        provider_name=recommended.name if recommended else None,
        provider_tier=recommended.model_tier.value if recommended else None,
    )
