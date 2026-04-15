"""多模型 A/B 测试 API — 同 Prompt 对比不同模型输出。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import require_permission

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ab-test", tags=["ab-test"])


class ABTestRequest(BaseModel):
    """A/B 测试请求。"""

    prompt: str = Field(..., min_length=1, max_length=10000, description="测试 Prompt")
    models: list[str] = Field(
        ..., min_length=2, max_length=5, description="模型列表（2-5 个）"
    )
    provider_name: str | None = Field(None, description="Provider 名称（可选）")
    max_tokens: int = Field(1024, ge=1, le=8192, description="最大输出 Token 数")


class ABTestModelResult(BaseModel):
    """单个模型的测试结果。"""

    model: str
    output: str
    latency_ms: int
    token_usage: dict[str, int]
    error: str | None = None


class ABTestResponse(BaseModel):
    """A/B 测试响应。"""

    prompt: str
    results: list[ABTestModelResult]


async def _resolve_provider_kwargs(
    db: AsyncSession,
    provider_name: str | None,
) -> dict[str, Any]:
    """从 provider_name 解析 LiteLLMProvider 构造参数。"""
    from app.core.crypto import decrypt_api_key
    from app.models.provider import ProviderConfig

    if provider_name:
        stmt = select(ProviderConfig).where(ProviderConfig.name == provider_name)
    else:
        stmt = select(ProviderConfig).where(ProviderConfig.is_enabled.is_(True)).limit(1)

    provider = (await db.execute(stmt)).scalar_one_or_none()
    if provider is None:
        return {}

    kwargs: dict[str, Any] = {}
    if provider.api_key_encrypted:
        try:
            kwargs["api_key"] = decrypt_api_key(provider.api_key_encrypted)
        except Exception:
            logger.warning("Provider '%s' API Key 解密失败", provider.name)
    if provider.base_url:
        kwargs["api_base"] = provider.base_url
    return kwargs


@router.post(
    "",
    response_model=ABTestResponse,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def run_ab_test(
    request: ABTestRequest,
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    """执行多模型 A/B 测试 — 并行调用多个模型并对比输出。"""
    from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
    from ckyclaw_framework.model.settings import ModelSettings

    provider_kwargs = await _resolve_provider_kwargs(db, request.provider_name)
    provider = LiteLLMProvider(**provider_kwargs)
    settings = ModelSettings(max_tokens=request.max_tokens)

    async def _call_model(model: str) -> ABTestModelResult:
        """调用单个模型并返回结果。"""
        start = time.monotonic()
        try:
            response = await provider.chat(
                model=model,
                messages=[{"role": "user", "content": request.prompt}],
                settings=settings,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = response.usage or {}
            return ABTestModelResult(
                model=model,
                output=response.content or "",
                latency_ms=elapsed_ms,
                token_usage={
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                },
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            # 只返回异常类名和摘要，避免泄露内部信息
            err_msg = f"{type(e).__name__}: {str(e)[:200]}"
            return ABTestModelResult(
                model=model,
                output="",
                latency_ms=elapsed_ms,
                token_usage={},
                error=err_msg,
            )

    # 并行调用所有模型
    tasks = [_call_model(m) for m in request.models]
    results = list(await asyncio.gather(*tasks))

    return ABTestResponse(prompt=request.prompt, results=results)
