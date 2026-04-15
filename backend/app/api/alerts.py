"""告警规则 & 告警事件 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.core.tenant import get_org_id
from app.schemas.alert import (
    VALID_SEVERITIES,
    AlertEventListResponse,
    AlertEventResponse,
    AlertRuleCheckResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from app.services import alert as alert_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/alert-rules", tags=["alerts"])


# ---------------------------------------------------------------------------
# AlertRule CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=AlertRuleListResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def list_rules(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_enabled: bool | None = Query(None),
    severity: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertRuleListResponse:
    """获取告警规则列表。"""
    if severity is not None and severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity 必须是 {VALID_SEVERITIES} 之一")
    rules, total = await alert_service.list_alert_rules(
        db, limit=limit, offset=offset, is_enabled=is_enabled, severity=severity, org_id=org_id,
    )
    return AlertRuleListResponse(data=[AlertRuleResponse.model_validate(r) for r in rules], total=total)


@router.post(
    "",
    response_model=AlertRuleResponse,
    status_code=201,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def create_rule(
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertRuleResponse:
    """创建告警规则。"""
    rule = await alert_service.create_alert_rule(db, data, org_id=org_id)
    return AlertRuleResponse.model_validate(rule)


@router.get(
    "/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def get_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertRuleResponse:
    """获取告警规则详情。"""
    rule = await alert_service.get_alert_rule(db, rule_id, org_id=org_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    return AlertRuleResponse.model_validate(rule)


@router.put(
    "/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[Depends(require_permission("agents", "write"))],
)
async def update_rule(
    rule_id: uuid.UUID,
    data: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertRuleResponse:
    """更新告警规则。"""
    rule = await alert_service.get_alert_rule(db, rule_id, org_id=org_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    rule = await alert_service.update_alert_rule(db, rule, data)
    return AlertRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=204, dependencies=[Depends(require_permission("agents", "delete"))])
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> None:
    """删除告警规则（软删除）。"""
    rule = await alert_service.get_alert_rule(db, rule_id, org_id=org_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    await alert_service.delete_alert_rule(db, rule)


# ---------------------------------------------------------------------------
# AlertEvent 查询
# ---------------------------------------------------------------------------


@router.get(
    "/{rule_id}/events",
    response_model=AlertEventListResponse,
    dependencies=[Depends(require_permission("agents", "read"))],
)
async def list_rule_events(
    rule_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertEventListResponse:
    """获取指定规则的告警事件列表。"""
    rule = await alert_service.get_alert_rule(db, rule_id, org_id=org_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    events, total = await alert_service.list_alert_events(db, rule_id=rule_id, limit=limit, offset=offset)
    return AlertEventListResponse(
        data=[AlertEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.post(
    "/{rule_id}/check",
    response_model=AlertRuleCheckResponse,
    status_code=200,
    dependencies=[Depends(require_permission("agents", "execute"))],
)
async def check_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: object = Depends(get_current_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AlertRuleCheckResponse:
    """手动触发告警规则检测。"""
    rule = await alert_service.get_alert_rule(db, rule_id, org_id=org_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    event = await alert_service.evaluate_rule(db, rule)
    if event is None:
        return AlertRuleCheckResponse(triggered=False, message="未触发告警")
    return AlertRuleCheckResponse(triggered=True, event_id=event.id, message=event.message)
