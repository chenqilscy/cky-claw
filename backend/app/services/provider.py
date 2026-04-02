"""Model Provider 业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_api_key
from app.core.exceptions import NotFoundError
from app.models.provider import ProviderConfig
from app.schemas.provider import ProviderCreate, ProviderUpdate


async def list_providers(
    db: AsyncSession,
    *,
    is_enabled: bool | None = None,
    provider_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ProviderConfig], int]:
    """获取 Provider 列表（分页 + 可选筛选）。"""
    base = select(ProviderConfig)
    if is_enabled is not None:
        base = base.where(ProviderConfig.is_enabled == is_enabled)
    if provider_type:
        base = base.where(ProviderConfig.provider_type == provider_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(ProviderConfig.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_provider(db: AsyncSession, provider_id: uuid.UUID) -> ProviderConfig:
    """按 ID 获取 Provider，不存在则 404。"""
    stmt = select(ProviderConfig).where(ProviderConfig.id == provider_id)
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider '{provider_id}' 不存在")
    return provider


async def create_provider(db: AsyncSession, data: ProviderCreate) -> ProviderConfig:
    """创建 Provider。API Key 加密后存储。"""
    provider = ProviderConfig(
        name=data.name,
        provider_type=data.provider_type,
        base_url=data.base_url,
        api_key_encrypted=encrypt_api_key(data.api_key),
        auth_type=data.auth_type,
        auth_config=data.auth_config,
        rate_limit_rpm=data.rate_limit_rpm,
        rate_limit_tpm=data.rate_limit_tpm,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def update_provider(
    db: AsyncSession, provider_id: uuid.UUID, data: ProviderUpdate
) -> ProviderConfig:
    """更新 Provider（PATCH 语义）。若提供 api_key 则重新加密存储。"""
    provider = await get_provider(db, provider_id)

    update_data = data.model_dump(exclude_unset=True)
    # api_key 特殊处理：加密后存储到 api_key_encrypted
    if "api_key" in update_data:
        new_key = update_data.pop("api_key")
        if new_key is not None:
            provider.api_key_encrypted = encrypt_api_key(new_key)

    for field, value in update_data.items():
        setattr(provider, field, value)

    provider.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(provider)
    return provider


async def delete_provider(db: AsyncSession, provider_id: uuid.UUID) -> None:
    """硬删除 Provider。"""
    provider = await get_provider(db, provider_id)
    await db.delete(provider)
    await db.commit()


async def toggle_provider(
    db: AsyncSession, provider_id: uuid.UUID, is_enabled: bool
) -> ProviderConfig:
    """启用/禁用 Provider。"""
    provider = await get_provider(db, provider_id)
    provider.is_enabled = is_enabled
    provider.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(provider)
    return provider
