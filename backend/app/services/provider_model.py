"""Provider Model 业务逻辑层。"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_model import ProviderModel
from app.schemas.provider_model import ProviderModelCreate, ProviderModelUpdate


async def list_models(
    db: AsyncSession,
    provider_id: uuid.UUID,
    *,
    is_enabled: bool | None = None,
) -> tuple[list[ProviderModel], int]:
    """获取 Provider 下的模型列表。"""
    base = select(ProviderModel).where(ProviderModel.provider_id == provider_id)
    if is_enabled is not None:
        base = base.where(ProviderModel.is_enabled == is_enabled)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(ProviderModel.model_name)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def create_model(
    db: AsyncSession,
    provider_id: uuid.UUID,
    data: ProviderModelCreate,
) -> ProviderModel:
    """创建模型配置。"""
    model = ProviderModel(
        provider_id=provider_id,
        model_name=data.model_name,
        display_name=data.display_name or data.model_name,
        context_window=data.context_window,
        max_output_tokens=data.max_output_tokens,
        prompt_price_per_1k=data.prompt_price_per_1k,
        completion_price_per_1k=data.completion_price_per_1k,
        is_enabled=data.is_enabled,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def get_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> ProviderModel:
    """获取模型配置。"""
    stmt = select(ProviderModel).where(ProviderModel.id == model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


async def update_model(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: ProviderModelUpdate,
) -> ProviderModel:
    """更新模型配置。"""
    model = await get_model(db, model_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)
    await db.commit()
    await db.refresh(model)
    return model


async def delete_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> None:
    """删除模型配置。"""
    model = await get_model(db, model_id)
    await db.delete(model)
    await db.commit()


async def get_model_by_name(
    db: AsyncSession,
    provider_id: uuid.UUID,
    model_name: str,
) -> ProviderModel | None:
    """按名称查询模型（用于成本计算）。"""
    stmt = select(ProviderModel).where(
        ProviderModel.provider_id == provider_id,
        ProviderModel.model_name == model_name,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
