"""Agent 多语言 Instructions API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.deps import require_permission
from app.schemas.agent_locale import (
    AgentLocaleCreate,
    AgentLocaleListResponse,
    AgentLocaleResponse,
    AgentLocaleUpdate,
)
from app.services import agent_locale as locale_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/agents/{name}/locales", tags=["agent-locales"])


@router.get(
    "",
    response_model=AgentLocaleListResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def list_locales(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> AgentLocaleListResponse:
    """获取 Agent 的所有语言版本 Instructions。"""
    locales = await locale_service.list_locales(db, name)
    return AgentLocaleListResponse(
        data=[AgentLocaleResponse.model_validate(loc) for loc in locales]
    )


@router.post(
    "",
    response_model=AgentLocaleResponse,
    status_code=201,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def create_locale(
    name: str,
    data: AgentLocaleCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentLocaleResponse:
    """为 Agent 新增一个语言版本的 Instructions。"""
    locale = await locale_service.create_locale(db, name, data)
    return AgentLocaleResponse.model_validate(locale)


@router.put(
    "/{locale}",
    response_model=AgentLocaleResponse,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def update_locale(
    name: str,
    locale: str,
    data: AgentLocaleUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentLocaleResponse:
    """更新指定语言版本的 Instructions。"""
    updated = await locale_service.update_locale(db, name, locale, data)
    return AgentLocaleResponse.model_validate(updated)


@router.delete(
    "/{locale}",
    status_code=204,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def delete_locale(
    name: str,
    locale: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除指定语言版本的 Instructions。默认语言版本不可删除。"""
    await locale_service.delete_locale(db, name, locale)
