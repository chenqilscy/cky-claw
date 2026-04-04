"""Model Provider 业务逻辑层。"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.core.exceptions import NotFoundError
from app.models.provider import ProviderConfig
from app.schemas.provider import ProviderCreate, ProviderUpdate

logger = logging.getLogger(__name__)


async def list_providers(
    db: AsyncSession,
    *,
    is_enabled: bool | None = None,
    provider_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ProviderConfig], int]:
    """获取 Provider 列表（分页 + 可选筛选）。"""
    base = select(ProviderConfig).where(ProviderConfig.is_deleted == False)  # noqa: E712
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
    stmt = select(ProviderConfig).where(
        ProviderConfig.id == provider_id, ProviderConfig.is_deleted == False  # noqa: E712
    )
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
    """软删除 Provider。"""
    provider = await get_provider(db, provider_id)
    provider.is_deleted = True
    provider.deleted_at = datetime.now(timezone.utc)
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


# 厂商类型 → LiteLLM 测试模型标识映射
_DEFAULT_TEST_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "azure": "azure/gpt-4o-mini",
    "deepseek": "deepseek/deepseek-chat",
    "qwen": "openai/qwen-turbo",
    "doubao": "openai/doubao-lite-32k",
    "zhipu": "openai/glm-4-flash",
    "moonshot": "openai/moonshot-v1-8k",
    "custom": "openai/default",
}


async def test_connection(
    db: AsyncSession,
    provider_id: uuid.UUID,
) -> dict:
    """测试 Provider 连通性：发送一个轻量请求验证 API Key + base_url 可用。

    Returns:
        dict: {success, latency_ms, error, model_used}
    """
    import litellm

    provider = await get_provider(db, provider_id)

    # 解密 API Key
    api_key: str | None = None
    if provider.api_key_encrypted:
        try:
            api_key = decrypt_api_key(provider.api_key_encrypted)
        except Exception:
            return {
                "success": False,
                "latency_ms": 0,
                "error": "API Key 解密失败，请重新配置",
                "model_used": None,
            }

    # 确定测试模型
    test_model = _DEFAULT_TEST_MODELS.get(provider.provider_type, "openai/default")

    # 构造请求参数
    kwargs: dict = {
        "model": test_model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if provider.base_url:
        kwargs["api_base"] = provider.base_url

    # 额外认证头
    if provider.auth_config:
        headers: dict[str, str] = {}
        for key, value in provider.auth_config.items():
            if isinstance(value, str) and value:
                try:
                    headers[key] = decrypt_api_key(value)
                except Exception:
                    headers[key] = value
        if headers:
            kwargs["extra_headers"] = headers

    start = time.monotonic()
    try:
        await litellm.acompletion(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        # 更新健康状态
        provider.health_status = "healthy"
        provider.last_health_check = datetime.now(timezone.utc)
        await db.commit()

        return {
            "success": True,
            "latency_ms": latency_ms,
            "error": None,
            "model_used": test_model,
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)

        # 更新健康状态
        provider.health_status = "unhealthy"
        provider.last_health_check = datetime.now(timezone.utc)
        await db.commit()

        return {
            "success": False,
            "latency_ms": latency_ms,
            "error": str(e),
            "model_used": test_model,
        }
