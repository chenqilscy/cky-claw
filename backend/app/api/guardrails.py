"""Guardrail 规则 CRUD API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.guardrail import (
    GuardrailRuleCreate,
    GuardrailRuleListResponse,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
)
from app.services import guardrail as guardrail_service

router = APIRouter(prefix="/api/v1/guardrails", tags=["guardrails"])


@router.post("", response_model=GuardrailRuleResponse, status_code=201)
async def create_guardrail_rule(
    body: GuardrailRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> GuardrailRuleResponse:
    """创建 Guardrail 规则。"""
    rule = await guardrail_service.create_guardrail_rule(
        db,
        name=body.name,
        description=body.description,
        type_=body.type,
        mode=body.mode,
        config=body.config,
    )
    await db.commit()
    return GuardrailRuleResponse.model_validate(rule)


@router.get("", response_model=GuardrailRuleListResponse)
async def list_guardrail_rules(
    type: str | None = Query(None, description="按类型筛选"),
    mode: str | None = Query(None, description="按模式筛选"),
    enabled_only: bool = Query(False, description="仅显示已启用"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> GuardrailRuleListResponse:
    """获取 Guardrail 规则列表。"""
    rules, total = await guardrail_service.list_guardrail_rules(
        db,
        type_filter=type,
        mode_filter=mode,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )
    items = [GuardrailRuleResponse.model_validate(r) for r in rules]
    return GuardrailRuleListResponse(data=items, total=total, limit=limit, offset=offset)


@router.get("/{rule_id}", response_model=GuardrailRuleResponse)
async def get_guardrail_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> GuardrailRuleResponse:
    """获取单个 Guardrail 规则。"""
    rule = await guardrail_service.get_guardrail_rule(db, rule_id)
    return GuardrailRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=GuardrailRuleResponse)
async def update_guardrail_rule(
    rule_id: uuid.UUID,
    body: GuardrailRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> GuardrailRuleResponse:
    """更新 Guardrail 规则。"""
    rule = await guardrail_service.update_guardrail_rule(
        db,
        rule_id,
        description=body.description,
        type_=body.type,
        mode=body.mode,
        config=body.config,
        is_enabled=body.is_enabled,
    )
    await db.commit()
    return GuardrailRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_guardrail_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除 Guardrail 规则。"""
    await guardrail_service.delete_guardrail_rule(db, rule_id)
    await db.commit()
