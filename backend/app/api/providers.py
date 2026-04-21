"""Model Provider 管理 API 路由。"""

from __future__ import annotations
import uuid

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.provider import (
    ProviderCreate,
    ProviderListResponse,
    ProviderResponse,
    ProviderRotateKey,
    ProviderTestResult,
    ProviderToggle,
    ProviderUpdate,
)
from app.services import provider as provider_service

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.provider import ProviderConfig
    from app.models.user import User

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


def _to_response(p: ProviderConfig) -> ProviderResponse:
    """将 ProviderConfig ORM 对象转为 ProviderResponse。"""
    return ProviderResponse(
        id=p.id,
        name=p.name,
        provider_type=p.provider_type,
        base_url=p.base_url,
        api_key_set=bool(p.api_key_encrypted),
        auth_type=p.auth_type,
        auth_config=p.auth_config,
        rate_limit_rpm=p.rate_limit_rpm,
        rate_limit_tpm=p.rate_limit_tpm,
        is_enabled=p.is_enabled,
        model_tier=p.model_tier,
        capabilities=p.capabilities,
        org_id=p.org_id,
        last_health_check=p.last_health_check,
        health_status=p.health_status,
        key_expires_at=p.key_expires_at,
        key_last_rotated_at=p.key_last_rotated_at,
        key_expired=(
            p.key_expires_at is not None
            and p.key_expires_at < datetime.now(UTC)
        ),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=ProviderListResponse)
async def list_providers(
    is_enabled: bool | None = Query(None, description="是否启用"),
    provider_type: str | None = Query(None, description="厂商类型"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderListResponse:
    """获取 Provider 列表。"""
    providers, total = await provider_service.list_providers(
        db, is_enabled=is_enabled, provider_type=provider_type, limit=limit, offset=offset
    )
    return ProviderListResponse(
        data=[_to_response(p) for p in providers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderResponse:
    """注册 Provider。"""
    provider = await provider_service.create_provider(db, data)
    return _to_response(provider)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderResponse:
    """获取 Provider 详情。"""
    provider = await provider_service.get_provider(db, provider_id)
    return _to_response(provider)


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderResponse:
    """更新 Provider。"""
    provider = await provider_service.update_provider(db, provider_id, data)
    return _to_response(provider)


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> dict[str, str]:
    """删除 Provider。"""
    await provider_service.delete_provider(db, provider_id)
    return {"message": "Provider 已删除"}


@router.put("/{provider_id}/toggle", response_model=ProviderResponse)
async def toggle_provider(
    provider_id: uuid.UUID,
    data: ProviderToggle,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderResponse:
    """启用/禁用 Provider。"""
    provider = await provider_service.toggle_provider(db, provider_id, data.is_enabled)
    return _to_response(provider)


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider_connection(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderTestResult:
    """测试 Provider 连通性。"""
    result = await provider_service.test_connection(db, provider_id)
    return ProviderTestResult(**result)


@router.post("/{provider_id}/rotate-key", response_model=ProviderResponse)
async def rotate_provider_key(
    provider_id: uuid.UUID,
    data: ProviderRotateKey,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ProviderResponse:
    """轮换 Provider API Key。原子性替换密钥并记录轮换时间。"""
    provider = await provider_service.rotate_key(
        db, provider_id, data.new_api_key, key_expires_at=data.key_expires_at,
    )
    return _to_response(provider)
