"""Organization 管理 API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services import organization as svc

router = APIRouter(prefix="/api/v1/organizations", tags=["组织"])


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> OrganizationListResponse:
    """查询组织列表。"""
    items, total = await svc.list_organizations(db, limit=limit, offset=offset, search=search)
    return OrganizationListResponse(
        data=[OrganizationResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> OrganizationResponse:
    """创建组织。"""
    record = await svc.create_organization(db, data)
    return OrganizationResponse.model_validate(record)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> OrganizationResponse:
    """获取单个组织。"""
    record = await svc.get_organization(db, org_id)
    if record is None:
        raise HTTPException(404, "organization not found")
    return OrganizationResponse.model_validate(record)


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> OrganizationResponse:
    """更新组织。"""
    record = await svc.update_organization(db, org_id, data)
    return OrganizationResponse.model_validate(record)


@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> None:
    """删除组织。"""
    ok = await svc.delete_organization(db, org_id)
    if not ok:
        raise HTTPException(404, "organization not found")
