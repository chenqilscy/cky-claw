"""Provider Model 业务逻辑层。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_api_key
from app.core.exceptions import NotFoundError
from app.models.provider import ProviderConfig
from app.models.provider_model import ProviderModel
from app.schemas.provider_model import ProviderModelCreate, ProviderModelUpdate

logger = logging.getLogger(__name__)


async def list_models(
    db: AsyncSession,
    provider_id: uuid.UUID,
    *,
    is_enabled: bool | None = None,
) -> tuple[list[ProviderModel], int]:
    """获取 Provider 下的模型列表。"""
    base = select(ProviderModel).where(
        ProviderModel.provider_id == provider_id, ProviderModel.is_deleted == False  # noqa: E712
    )
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
    stmt = select(ProviderModel).where(
        ProviderModel.id == model_id, ProviderModel.is_deleted == False  # noqa: E712
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        raise NotFoundError(f"模型 '{model_id}' 不存在")
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
    """软删除模型配置。"""
    model = await get_model(db, model_id)
    model.is_deleted = True
    model.deleted_at = datetime.now(timezone.utc)
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


async def sync_models_from_provider(
    db: AsyncSession,
    provider_id: uuid.UUID,
) -> dict[str, Any]:
    """从模型厂商的 /v1/models 端点同步模型列表。

    通过 OpenAI 兼容接口获取厂商支持的模型名称，然后批量 upsert 到数据库。

    Returns:
        dict: {synced: int, created: int, updated: int, errors: list[str]}
    """
    stmt = select(ProviderConfig).where(ProviderConfig.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider '{provider_id}' 不存在")

    base_url = (provider.base_url or "").rstrip("/")
    if not base_url:
        return {"synced": 0, "created": 0, "updated": 0, "errors": ["Provider 未配置 base_url"]}

    # 解密 API Key
    api_key: str | None = None
    if provider.api_key_encrypted:
        try:
            api_key = decrypt_api_key(provider.api_key_encrypted)
        except Exception:
            return {"synced": 0, "created": 0, "updated": 0, "errors": ["API Key 解密失败"]}

    # 调用 /v1/models 端点
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 额外认证头
    if provider.auth_config:
        for key, value in provider.auth_config.items():
            if isinstance(value, str) and value:
                try:
                    headers[key] = decrypt_api_key(value)
                except Exception:
                    headers[key] = value

    models_url = f"{base_url}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(models_url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as e:
        return {"synced": 0, "created": 0, "updated": 0, "errors": [f"HTTP {e.response.status_code}: {e.response.text[:200]}"]}
    except Exception as e:
        return {"synced": 0, "created": 0, "updated": 0, "errors": [f"请求失败: {e}"]}

    # 解析模型列表（OpenAI 格式: { data: [ { id: "model-name", ... } ] }）
    raw_models: list[dict[str, Any]] = payload.get("data", [])
    if not raw_models:
        return {"synced": 0, "created": 0, "updated": 0, "errors": ["厂商返回空模型列表"]}

    # 查询现有模型
    existing_stmt = select(ProviderModel).where(
        ProviderModel.provider_id == provider_id,
        ProviderModel.is_deleted == False,  # noqa: E712
    )
    existing_rows = (await db.execute(existing_stmt)).scalars().all()
    existing_map = {m.model_name: m for m in existing_rows}

    created = 0
    updated = 0
    errors: list[str] = []

    for raw in raw_models:
        model_id_str = raw.get("id") or raw.get("model")
        if not model_id_str or not isinstance(model_id_str, str):
            continue

        try:
            if model_id_str in existing_map:
                # 已存在，更新 display_name（如果远端有）
                existing = existing_map[model_id_str]
                owned_by = raw.get("owned_by", "")
                if owned_by and not existing.display_name:
                    existing.display_name = f"{model_id_str} ({owned_by})"
                    updated += 1
            else:
                # 不存在，创建新记录
                owned_by = raw.get("owned_by", "")
                display = f"{model_id_str} ({owned_by})" if owned_by else model_id_str
                new_model = ProviderModel(
                    provider_id=provider_id,
                    model_name=model_id_str,
                    display_name=display,
                    context_window=4096,
                    is_enabled=True,
                )
                db.add(new_model)
                created += 1
        except Exception as e:
            errors.append(f"处理模型 '{model_id_str}' 失败: {e}")

    await db.commit()
    return {"synced": created + updated, "created": created, "updated": updated, "errors": errors}
