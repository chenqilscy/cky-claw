"""Organization 服务层。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.exceptions import ConflictError, NotFoundError
from app.models.organization import Organization

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.organization import OrganizationCreate, OrganizationUpdate


async def list_organizations(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[Organization], int]:
    """查询组织列表。"""
    base = select(Organization).where(Organization.is_deleted == False)  # noqa: E712

    if search:
        like = f"%{search}%"
        base = base.where(Organization.name.ilike(like) | Organization.slug.ilike(like))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    items = (
        await db.execute(
            base.order_by(Organization.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(items), total


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    """按 ID 获取组织。"""
    return (await db.execute(
        select(Organization).where(
            Organization.id == org_id, Organization.is_deleted == False  # noqa: E712
        )
    )).scalar_one_or_none()


async def get_organization_by_slug(db: AsyncSession, slug: str) -> Organization | None:
    """按 slug 获取组织。"""
    return (await db.execute(select(Organization).where(
        Organization.slug == slug, Organization.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    """创建组织。"""
    existing = await get_organization_by_slug(db, data.slug)
    if existing:
        raise ConflictError(f"slug '{data.slug}' 已存在")

    record = Organization(
        name=data.name,
        slug=data.slug,
        description=data.description,
        settings=data.settings,
        quota=data.quota,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def update_organization(
    db: AsyncSession, org_id: uuid.UUID, data: OrganizationUpdate
) -> Organization:
    """更新组织。"""
    record = await get_organization(db, org_id)
    if record is None:
        raise NotFoundError("组织不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return record


async def delete_organization(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """软删除组织。"""
    record = await get_organization(db, org_id)
    if record is None:
        return False
    record.is_deleted = True
    record.deleted_at = datetime.now(UTC)
    await db.commit()
    return True
