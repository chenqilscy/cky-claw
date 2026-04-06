"""进化建议业务逻辑。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.evolution import EvolutionProposalRecord
from app.schemas.evolution import EvolutionProposalCreate, EvolutionProposalUpdate

# 合法的状态转换矩阵
_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"approved", "rejected"},
    "approved": {"applied"},
    "applied": {"rolled_back"},
}


async def list_proposals(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    proposal_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[EvolutionProposalRecord], int]:
    """获取进化建议列表（分页 + 可选筛选）。"""
    base = select(EvolutionProposalRecord)

    if agent_name:
        base = base.where(EvolutionProposalRecord.agent_name == agent_name)
    if proposal_type:
        base = base.where(EvolutionProposalRecord.proposal_type == proposal_type)
    if status:
        base = base.where(EvolutionProposalRecord.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(EvolutionProposalRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> EvolutionProposalRecord:
    """按 ID 获取进化建议，不存在则 404。"""
    stmt = select(EvolutionProposalRecord).where(
        EvolutionProposalRecord.id == proposal_id
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"进化建议 '{proposal_id}' 不存在")
    return record


async def create_proposal(
    db: AsyncSession,
    data: EvolutionProposalCreate,
) -> EvolutionProposalRecord:
    """创建进化建议。"""
    record = EvolutionProposalRecord(
        agent_name=data.agent_name,
        proposal_type=data.proposal_type,
        trigger_reason=data.trigger_reason,
        current_value=data.current_value,
        proposed_value=data.proposed_value,
        confidence_score=data.confidence_score,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def update_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    data: EvolutionProposalUpdate,
) -> EvolutionProposalRecord:
    """更新进化建议（PATCH 语义 + 状态机校验）。"""
    record = await get_proposal(db, proposal_id)

    update_data = data.model_dump(exclude_unset=True)

    # 状态变更校验
    if "status" in update_data and update_data["status"] is not None:
        new_status = update_data["status"]
        allowed = _TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"不允许从 '{record.status}' 转换到 '{new_status}'，"
                f"允许的目标: {allowed or '无'}"
            )
        record.status = new_status
        if new_status == "applied":
            record.applied_at = datetime.now(timezone.utc)
        elif new_status == "rolled_back":
            record.rolled_back_at = datetime.now(timezone.utc)

    if "eval_before" in update_data:
        record.eval_before = update_data["eval_before"]
    if "eval_after" in update_data:
        record.eval_after = update_data["eval_after"]
    if "metadata" in update_data and update_data["metadata"] is not None:
        record.metadata_ = update_data["metadata"]

    record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> None:
    """删除进化建议（硬删除）。"""
    record = await get_proposal(db, proposal_id)
    await db.delete(record)
    await db.commit()
