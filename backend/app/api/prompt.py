"""Prompt 模板 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.schemas.prompt import (
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptValidateRequest,
    PromptValidateResponse,
)
from app.services import agent as agent_service
from app.services import prompt as prompt_service

router = APIRouter(prefix="/api/v1/agents", tags=["prompt"])


@router.post(
    "/{name}/prompt/preview",
    response_model=PromptPreviewResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def preview_agent_prompt(
    name: str,
    body: PromptPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptPreviewResponse:
    """渲染指定 Agent 的 Prompt 模板预览。"""
    agent = await agent_service.get_agent_by_name(db, name)
    result = prompt_service.preview_prompt(
        instructions=agent.instructions,
        variables=body.variables,
        definitions=agent.prompt_variables,
    )
    return PromptPreviewResponse(**result)


@router.post(
    "/{name}/prompt/validate",
    response_model=PromptValidateResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def validate_agent_prompt(
    name: str,
    body: PromptValidateRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptValidateResponse:
    """校验 Prompt 模板与变量定义是否一致。"""
    await agent_service.get_agent_by_name(db, name)
    result = prompt_service.validate_prompt(
        instructions=body.instructions,
        definitions=body.variables,
    )
    return PromptValidateResponse(**result)
