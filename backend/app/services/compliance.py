"""Compliance 合规框架业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.compliance import (
    ComplianceControlPoint,
    DataClassification,
    DataClassificationLabel,
    ErasureRequest,
    ErasureStatus,
    RetentionPolicy,
    RetentionStatus,
)


# ─── 数据分类标签 ───

async def create_label(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
    classification: str,
    reason: str = "",
    auto_detected: bool = False,
) -> DataClassificationLabel:
    """创建数据分类标签。"""
    label = DataClassificationLabel(
        resource_type=resource_type,
        resource_id=resource_id,
        classification=DataClassification(classification),
        reason=reason,
        auto_detected=auto_detected,
    )
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return label


async def list_labels(
    db: AsyncSession,
    *,
    resource_type: str | None = None,
    classification: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DataClassificationLabel], int]:
    """查询分类标签列表。"""
    base = select(DataClassificationLabel).where(
        DataClassificationLabel.is_deleted == False,  # noqa: E712
    )
    if resource_type:
        base = base.where(DataClassificationLabel.resource_type == resource_type)
    if classification:
        base = base.where(DataClassificationLabel.classification == DataClassification(classification))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(DataClassificationLabel.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(rows), total


# ─── 数据保留策略 ───

async def create_retention_policy(
    db: AsyncSession,
    resource_type: str,
    classification: str,
    retention_days: int,
) -> RetentionPolicy:
    """创建保留策略。"""
    policy = RetentionPolicy(
        resource_type=resource_type,
        classification=DataClassification(classification),
        retention_days=retention_days,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def list_retention_policies(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RetentionPolicy], int]:
    """查询保留策略列表。"""
    base = select(RetentionPolicy).where(RetentionPolicy.is_deleted == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(RetentionPolicy.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(rows), total


async def update_retention_policy(
    db: AsyncSession,
    policy_id: uuid.UUID,
    *,
    retention_days: int | None = None,
    status: str | None = None,
) -> RetentionPolicy:
    """更新保留策略。"""
    stmt = select(RetentionPolicy).where(
        RetentionPolicy.id == policy_id,
        RetentionPolicy.is_deleted == False,  # noqa: E712
    )
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if not policy:
        raise NotFoundError("保留策略不存在")
    if retention_days is not None:
        policy.retention_days = retention_days
    if status is not None:
        policy.status = RetentionStatus(status)
    await db.commit()
    await db.refresh(policy)
    return policy


# ─── Right-to-Erasure ───

async def create_erasure_request(
    db: AsyncSession,
    requester_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> ErasureRequest:
    """创建删除请求。"""
    # 检查是否已有 pending 请求
    existing = await db.execute(
        select(ErasureRequest).where(
            ErasureRequest.target_user_id == target_user_id,
            ErasureRequest.status == ErasureStatus.PENDING,
            ErasureRequest.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("该用户已有待处理的删除请求")

    req = ErasureRequest(
        requester_user_id=requester_user_id,
        target_user_id=target_user_id,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


async def list_erasure_requests(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ErasureRequest], int]:
    """查询删除请求列表。"""
    base = select(ErasureRequest).where(ErasureRequest.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(ErasureRequest.status == ErasureStatus(status))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(ErasureRequest.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(rows), total


async def process_erasure_request(
    db: AsyncSession,
    request_id: uuid.UUID,
    scanned: int,
    deleted: int,
    report: dict | None = None,
) -> ErasureRequest:
    """处理删除请求（标记完成）。"""
    stmt = select(ErasureRequest).where(
        ErasureRequest.id == request_id,
        ErasureRequest.is_deleted == False,  # noqa: E712
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise NotFoundError("删除请求不存在")
    req.status = ErasureStatus.COMPLETED
    req.scanned_resources = scanned
    req.deleted_resources = deleted
    req.report = report
    req.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(req)
    return req


# ─── SOC2 控制点 ───

async def create_control_point(
    db: AsyncSession,
    control_id: str,
    category: str,
    description: str,
    implementation: str = "",
    evidence_links: dict | None = None,
) -> ComplianceControlPoint:
    """创建控制点。"""
    cp = ComplianceControlPoint(
        control_id=control_id,
        category=category,
        description=description,
        implementation=implementation,
        evidence_links=evidence_links,
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return cp


async def list_control_points(
    db: AsyncSession,
    *,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ComplianceControlPoint], int]:
    """查询控制点列表。"""
    base = select(ComplianceControlPoint).where(
        ComplianceControlPoint.is_deleted == False  # noqa: E712
    )
    if category:
        base = base.where(ComplianceControlPoint.category == category)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(ComplianceControlPoint.control_id.asc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(rows), total


async def update_control_point(
    db: AsyncSession,
    point_id: uuid.UUID,
    *,
    implementation: str | None = None,
    evidence_links: dict | None = None,
    is_satisfied: bool | None = None,
) -> ComplianceControlPoint:
    """更新控制点。"""
    stmt = select(ComplianceControlPoint).where(
        ComplianceControlPoint.id == point_id,
        ComplianceControlPoint.is_deleted == False,  # noqa: E712
    )
    cp = (await db.execute(stmt)).scalar_one_or_none()
    if not cp:
        raise NotFoundError("控制点不存在")
    if implementation is not None:
        cp.implementation = implementation
    if evidence_links is not None:
        cp.evidence_links = evidence_links
    if is_satisfied is not None:
        cp.is_satisfied = is_satisfied
    await db.commit()
    await db.refresh(cp)
    return cp


# ─── 合规仪表盘 ───

async def get_dashboard(db: AsyncSession) -> dict:
    """获取合规仪表盘汇总数据。"""
    # 控制点统计
    cp_base = select(ComplianceControlPoint).where(
        ComplianceControlPoint.is_deleted == False  # noqa: E712
    )
    total_cp = (await db.execute(select(func.count()).select_from(cp_base.subquery()))).scalar_one()
    satisfied_cp = (await db.execute(
        select(func.count()).select_from(
            cp_base.where(ComplianceControlPoint.is_satisfied == True).subquery()  # noqa: E712
        )
    )).scalar_one()

    # 保留策略统计
    active_policies = (await db.execute(
        select(func.count()).select_from(
            select(RetentionPolicy).where(
                RetentionPolicy.is_deleted == False,  # noqa: E712
                RetentionPolicy.status == RetentionStatus.ACTIVE,
            ).subquery()
        )
    )).scalar_one()

    # 删除请求统计
    pending_erasures = (await db.execute(
        select(func.count()).select_from(
            select(ErasureRequest).where(
                ErasureRequest.is_deleted == False,  # noqa: E712
                ErasureRequest.status == ErasureStatus.PENDING,
            ).subquery()
        )
    )).scalar_one()

    # 分类标签统计
    cls_rows = (await db.execute(
        select(
            DataClassificationLabel.classification,
            func.count(DataClassificationLabel.id),
        ).where(
            DataClassificationLabel.is_deleted == False  # noqa: E712
        ).group_by(DataClassificationLabel.classification)
    )).all()
    classification_summary = {str(row[0].value): int(row[1]) for row in cls_rows}

    return {
        "total_control_points": total_cp,
        "satisfied_control_points": satisfied_cp,
        "satisfaction_rate": round(satisfied_cp / total_cp, 2) if total_cp else 0.0,
        "active_retention_policies": active_policies,
        "pending_erasure_requests": pending_erasures,
        "classification_summary": classification_summary,
    }
