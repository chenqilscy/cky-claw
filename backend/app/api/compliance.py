"""Compliance 合规框架 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.schemas.compliance import (
    ClassificationLabelCreate,
    ClassificationLabelListResponse,
    ClassificationLabelResponse,
    ComplianceDashboardResponse,
    ControlPointCreate,
    ControlPointListResponse,
    ControlPointResponse,
    ControlPointUpdate,
    ErasureRequestCreate,
    ErasureRequestListResponse,
    ErasureRequestResponse,
    RetentionPolicyCreate,
    RetentionPolicyListResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)
from app.services import compliance as comp_svc

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ─── 合规仪表盘 ───

@router.get(
    "/dashboard",
    response_model=ComplianceDashboardResponse,
    dependencies=[Depends(require_permission("compliance", "read"))],
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
) -> ComplianceDashboardResponse:
    """获取合规仪表盘汇总数据。"""
    data = await comp_svc.get_dashboard(db)
    return ComplianceDashboardResponse(**data)


# ─── 数据分类标签 ───

@router.post(
    "/labels",
    response_model=ClassificationLabelResponse,
    status_code=201,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def create_label(
    body: ClassificationLabelCreate,
    db: AsyncSession = Depends(get_db),
) -> ClassificationLabelResponse:
    """创建数据分类标签。"""
    label = await comp_svc.create_label(
        db,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        classification=body.classification,
        reason=body.reason,
    )
    return ClassificationLabelResponse.model_validate(label)


@router.get(
    "/labels",
    response_model=ClassificationLabelListResponse,
    dependencies=[Depends(require_permission("compliance", "read"))],
)
async def list_labels(
    resource_type: str | None = Query(None),
    classification: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ClassificationLabelListResponse:
    """查询数据分类标签列表。"""
    rows, total = await comp_svc.list_labels(
        db, resource_type=resource_type, classification=classification,
        limit=limit, offset=offset,
    )
    return ClassificationLabelListResponse(
        data=[ClassificationLabelResponse.model_validate(r) for r in rows],
        total=total,
    )


# ─── 数据保留策略 ───

@router.post(
    "/retention-policies",
    response_model=RetentionPolicyResponse,
    status_code=201,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def create_retention_policy(
    body: RetentionPolicyCreate,
    db: AsyncSession = Depends(get_db),
) -> RetentionPolicyResponse:
    """创建数据保留策略。"""
    policy = await comp_svc.create_retention_policy(
        db,
        resource_type=body.resource_type,
        classification=body.classification,
        retention_days=body.retention_days,
    )
    return RetentionPolicyResponse.model_validate(policy)


@router.get(
    "/retention-policies",
    response_model=RetentionPolicyListResponse,
    dependencies=[Depends(require_permission("compliance", "read"))],
)
async def list_retention_policies(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RetentionPolicyListResponse:
    """查询数据保留策略列表。"""
    rows, total = await comp_svc.list_retention_policies(db, limit=limit, offset=offset)
    return RetentionPolicyListResponse(
        data=[RetentionPolicyResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.put(
    "/retention-policies/{policy_id}",
    response_model=RetentionPolicyResponse,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def update_retention_policy(
    policy_id: uuid.UUID,
    body: RetentionPolicyUpdate,
    db: AsyncSession = Depends(get_db),
) -> RetentionPolicyResponse:
    """更新数据保留策略。"""
    policy = await comp_svc.update_retention_policy(
        db, policy_id,
        retention_days=body.retention_days,
        status=body.status,
    )
    return RetentionPolicyResponse.model_validate(policy)


# ─── Right-to-Erasure ───

@router.post(
    "/erasure-requests",
    response_model=ErasureRequestResponse,
    status_code=201,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def create_erasure_request(
    body: ErasureRequestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ErasureRequestResponse:
    """创建 Right-to-Erasure 删除请求。"""
    req = await comp_svc.create_erasure_request(db, user.id, body.target_user_id)
    return ErasureRequestResponse.model_validate(req)


@router.get(
    "/erasure-requests",
    response_model=ErasureRequestListResponse,
    dependencies=[Depends(require_permission("compliance", "read"))],
)
async def list_erasure_requests(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ErasureRequestListResponse:
    """查询删除请求列表。"""
    rows, total = await comp_svc.list_erasure_requests(
        db, status=status, limit=limit, offset=offset,
    )
    return ErasureRequestListResponse(
        data=[ErasureRequestResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.post(
    "/erasure-requests/{request_id}/complete",
    response_model=ErasureRequestResponse,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def complete_erasure_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ErasureRequestResponse:
    """标记删除请求为已完成。"""
    req = await comp_svc.process_erasure_request(db, request_id, scanned=0, deleted=0)
    return ErasureRequestResponse.model_validate(req)


# ─── SOC2 控制点 ───

@router.post(
    "/control-points",
    response_model=ControlPointResponse,
    status_code=201,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def create_control_point(
    body: ControlPointCreate,
    db: AsyncSession = Depends(get_db),
) -> ControlPointResponse:
    """创建 SOC2 控制点。"""
    cp = await comp_svc.create_control_point(
        db,
        control_id=body.control_id,
        category=body.category,
        description=body.description,
        implementation=body.implementation,
        evidence_links=body.evidence_links,
    )
    return ControlPointResponse.model_validate(cp)


@router.get(
    "/control-points",
    response_model=ControlPointListResponse,
    dependencies=[Depends(require_permission("compliance", "read"))],
)
async def list_control_points(
    category: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ControlPointListResponse:
    """查询 SOC2 控制点列表。"""
    rows, total = await comp_svc.list_control_points(
        db, category=category, limit=limit, offset=offset,
    )
    return ControlPointListResponse(
        data=[ControlPointResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.put(
    "/control-points/{point_id}",
    response_model=ControlPointResponse,
    dependencies=[Depends(require_permission("compliance", "write"))],
)
async def update_control_point(
    point_id: uuid.UUID,
    body: ControlPointUpdate,
    db: AsyncSession = Depends(get_db),
) -> ControlPointResponse:
    """更新 SOC2 控制点。"""
    cp = await comp_svc.update_control_point(
        db, point_id,
        implementation=body.implementation,
        evidence_links=body.evidence_links,
        is_satisfied=body.is_satisfied,
    )
    return ControlPointResponse.model_validate(cp)
