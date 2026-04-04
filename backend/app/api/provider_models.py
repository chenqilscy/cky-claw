"""Provider Model 管理 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.provider_model import (
    ProviderModelCreate,
    ProviderModelListResponse,
    ProviderModelResponse,
    ProviderModelUpdate,
)
from app.services import provider_model as pm_service

router = APIRouter(prefix="/api/v1/providers", tags=["provider-models"])


@router.get("/{provider_id}/models", response_model=ProviderModelListResponse)
async def list_provider_models(
    provider_id: uuid.UUID,
    is_enabled: bool | None = Query(None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderModelListResponse:
    """获取 Provider 下的模型列表。"""
    models, total = await pm_service.list_models(db, provider_id, is_enabled=is_enabled)
    return ProviderModelListResponse(
        data=[ProviderModelResponse.model_validate(m) for m in models],
        total=total,
    )


@router.post("/{provider_id}/models", response_model=ProviderModelResponse, status_code=201)
async def create_provider_model(
    provider_id: uuid.UUID,
    data: ProviderModelCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderModelResponse:
    """创建 Provider Model。"""
    model = await pm_service.create_model(db, provider_id, data)
    return ProviderModelResponse.model_validate(model)


@router.get("/{provider_id}/models/{model_id}", response_model=ProviderModelResponse)
async def get_provider_model(
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderModelResponse:
    """获取 Provider Model 详情。"""
    model = await pm_service.get_model(db, model_id)
    return ProviderModelResponse.model_validate(model)


@router.put("/{provider_id}/models/{model_id}", response_model=ProviderModelResponse)
async def update_provider_model(
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    data: ProviderModelUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderModelResponse:
    """更新 Provider Model。"""
    model = await pm_service.update_model(db, model_id, data)
    return ProviderModelResponse.model_validate(model)


@router.delete("/{provider_id}/models/{model_id}")
async def delete_provider_model(
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> dict[str, str]:
    """删除 Provider Model。"""
    await pm_service.delete_model(db, model_id)
    return {"message": "Model deleted"}
