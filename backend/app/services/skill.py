"""Skill 技能知识包业务逻辑层。"""

from __future__ import annotations

import json  # noqa: F401 – used elsewhere
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.skill import SkillRecord
from app.schemas.skill import SkillCreate, SkillSearchRequest, SkillUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_skill(db: AsyncSession, data: SkillCreate) -> SkillRecord:
    """创建技能知识包。"""
    record = SkillRecord(
        name=data.name,
        version=data.version,
        description=data.description,
        content=data.content,
        category=data.category.value,
        tags=data.tags,
        applicable_agents=data.applicable_agents,
        author=data.author,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_skill(db: AsyncSession, skill_id: uuid.UUID) -> SkillRecord:
    """获取单个技能。"""
    stmt = select(SkillRecord).where(
        SkillRecord.id == skill_id, SkillRecord.is_deleted == False  # noqa: E712
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"技能 '{skill_id}' 不存在")
    return record


async def get_skill_by_name(db: AsyncSession, name: str) -> SkillRecord:
    """按名称获取技能。"""
    stmt = select(SkillRecord).where(SkillRecord.name == name)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"技能 '{name}' 不存在")
    return record


async def list_skills(
    db: AsyncSession,
    *,
    category: str | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[SkillRecord], int]:
    """获取技能列表（分页 + 过滤）。"""
    base = select(SkillRecord).where(SkillRecord.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(SkillRecord.org_id == org_id)
    if category:
        base = base.where(SkillRecord.category == category)
    if tag:
        # JSONB @> 操作符：tags 包含指定标签
        base = base.where(SkillRecord.tags.op("@>")(json.dumps([tag])))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(SkillRecord.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def update_skill(
    db: AsyncSession, skill_id: uuid.UUID, data: SkillUpdate
) -> SkillRecord:
    """更新技能。"""
    record = await get_skill(db, skill_id)
    update_data = data.model_dump(exclude_unset=True)
    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = update_data["category"].value
    for key, value in update_data.items():
        if key == "metadata":
            setattr(record, "metadata_", value)
        else:
            setattr(record, key, value)
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_skill(db: AsyncSession, skill_id: uuid.UUID) -> None:
    """软删除技能。"""
    record = await get_skill(db, skill_id)
    record.is_deleted = True
    record.deleted_at = datetime.now(timezone.utc)
    await db.commit()


def _escape_like(query: str) -> str:
    """转义 LIKE/ILIKE 通配符，防止 SQL 通配符注入。"""
    return query.replace("%", "\\%").replace("_", "\\_")


async def search_skills(
    db: AsyncSession, data: SkillSearchRequest
) -> list[SkillRecord]:
    """关键词搜索技能（名称 + 描述 + 标签）。"""
    escaped = _escape_like(data.query)
    pattern = f"%{escaped}%"
    base = select(SkillRecord).where(
        or_(
            SkillRecord.name.ilike(pattern),
            SkillRecord.description.ilike(pattern),
        )
    )
    if data.category:
        base = base.where(SkillRecord.category == data.category.value)
    base = base.order_by(SkillRecord.updated_at.desc()).limit(data.limit)
    rows = (await db.execute(base)).scalars().all()
    return list(rows)


async def find_skills_for_agent(
    db: AsyncSession, agent_name: str
) -> list[SkillRecord]:
    """查找适用于指定 Agent 的所有技能。

    规则：applicable_agents 为空列表 → 适用所有 Agent；
         非空列表 → 仅适用于列表中包含的 Agent。
    """
    stmt = select(SkillRecord).where(
        or_(
            # 空数组 → 适用所有 Agent
            SkillRecord.applicable_agents == [],
            # JSONB 包含指定 Agent 名称
            SkillRecord.applicable_agents.op("@>")(json.dumps([agent_name])),
        )
    ).order_by(SkillRecord.name)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
