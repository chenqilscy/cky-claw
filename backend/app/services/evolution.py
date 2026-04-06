"""进化建议 & 信号业务逻辑。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.evolution import EvolutionProposalRecord, EvolutionSignalRecord
from app.schemas.evolution import (
    EvolutionProposalCreate,
    EvolutionProposalUpdate,
    EvolutionSignalCreate,
)

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

        if new_status == "applied":
            # 应用建议到 Agent 配置（内部处理状态变更和快照）
            record.status = "approved"  # 先设为 approved 以满足 apply 前置条件
            await db.flush()
            result = await apply_proposal_to_agent(db, record.id)
            # apply_proposal_to_agent 已经 commit + refresh，
            # 若还有 eval_before/eval_after/metadata 更新，需要额外处理
            if "eval_before" in update_data:
                result.eval_before = update_data["eval_before"]
            if "eval_after" in update_data:
                result.eval_after = update_data["eval_after"]
            if "metadata" in update_data and update_data["metadata"] is not None:
                result.metadata_ = update_data["metadata"]
            if any(k in update_data for k in ("eval_before", "eval_after", "metadata")):
                await db.commit()
                await db.refresh(result)
            return result
        else:
            record.status = new_status
            if new_status == "rolled_back":
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


# ────────────────────────────────────────────────────────────────
# 信号 CRUD
# ────────────────────────────────────────────────────────────────


async def create_signal(
    db: AsyncSession,
    data: EvolutionSignalCreate,
) -> EvolutionSignalRecord:
    """上报一条进化信号。"""
    record = EvolutionSignalRecord(
        agent_name=data.agent_name,
        signal_type=data.signal_type,
        tool_name=data.tool_name,
        call_count=data.call_count,
        success_count=data.success_count,
        failure_count=data.failure_count,
        avg_duration_ms=data.avg_duration_ms,
        overall_score=data.overall_score,
        negative_rate=data.negative_rate,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def create_signals_batch(
    db: AsyncSession,
    signals: list[EvolutionSignalCreate],
) -> list[EvolutionSignalRecord]:
    """批量上报进化信号。"""
    records = []
    for data in signals:
        record = EvolutionSignalRecord(
            agent_name=data.agent_name,
            signal_type=data.signal_type,
            tool_name=data.tool_name,
            call_count=data.call_count,
            success_count=data.success_count,
            failure_count=data.failure_count,
            avg_duration_ms=data.avg_duration_ms,
            overall_score=data.overall_score,
            negative_rate=data.negative_rate,
            metadata_=data.metadata,
        )
        db.add(record)
        records.append(record)
    await db.commit()
    for r in records:
        await db.refresh(r)
    return records


async def list_signals(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    signal_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[EvolutionSignalRecord], int]:
    """获取进化信号列表（分页 + 可选筛选）。"""
    base = select(EvolutionSignalRecord)

    if agent_name:
        base = base.where(EvolutionSignalRecord.agent_name == agent_name)
    if signal_type:
        base = base.where(EvolutionSignalRecord.signal_type == signal_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(EvolutionSignalRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def analyze_agent(
    db: AsyncSession,
    agent_name: str,
) -> list[EvolutionProposalRecord]:
    """对指定 Agent 执行策略分析。

    从数据库读取该 Agent 的所有信号，通过 Framework StrategyEngine 生成
    优化建议，并将建议持久化到数据库。

    Returns:
        生成的建议列表。
    """
    from ckyclaw_framework.evolution import (
        EvolutionConfig,
        MetricSignal,
        SignalType,
        StrategyEngine,
        ToolPerformanceSignal,
    )

    # 读取该 Agent 的所有信号
    stmt = (
        select(EvolutionSignalRecord)
        .where(EvolutionSignalRecord.agent_name == agent_name)
        .order_by(EvolutionSignalRecord.created_at.desc())
        .limit(1000)
    )
    rows = (await db.execute(stmt)).scalars().all()

    # 转换为 Framework EvolutionSignal
    from ckyclaw_framework.evolution.signals import EvolutionSignal, FeedbackSignal

    signals: list[EvolutionSignal] = []
    for row in rows:
        if row.signal_type == "tool_performance":
            signals.append(
                ToolPerformanceSignal(
                    signal_type=SignalType.TOOL_PERFORMANCE,
                    agent_name=row.agent_name,
                    timestamp=row.created_at,
                    tool_name=row.tool_name or "",
                    call_count=row.call_count,
                    success_count=row.success_count,
                    failure_count=row.failure_count,
                    avg_duration_ms=row.avg_duration_ms,
                    metadata=row.metadata_,
                )
            )
        elif row.signal_type == "evaluation":
            signals.append(
                MetricSignal(
                    signal_type=SignalType.EVALUATION,
                    agent_name=row.agent_name,
                    timestamp=row.created_at,
                    overall_score=row.overall_score or 0.0,
                    sample_count=row.call_count,
                    metadata=row.metadata_,
                )
            )
        elif row.signal_type == "feedback":
            signals.append(
                FeedbackSignal(
                    signal_type=SignalType.FEEDBACK,
                    agent_name=row.agent_name,
                    timestamp=row.created_at,
                    positive_count=row.success_count,
                    negative_count=row.failure_count,
                    total_count=row.call_count,
                    metadata=row.metadata_,
                )
            )

    if not signals:
        return []

    # 运行策略引擎
    config = EvolutionConfig(enabled=True)
    engine = StrategyEngine(config=config)
    proposals = engine.generate_proposals(agent_name, signals)

    # 持久化建议到数据库
    created: list[EvolutionProposalRecord] = []
    for proposal in proposals:
        record = EvolutionProposalRecord(
            agent_name=proposal.agent_name,
            proposal_type=proposal.proposal_type.value,
            trigger_reason=proposal.trigger_reason,
            current_value=proposal.current_value if isinstance(proposal.current_value, dict) else None,
            proposed_value=proposal.proposed_value if isinstance(proposal.proposed_value, dict) else None,
            confidence_score=proposal.confidence_score,
            metadata_=proposal.metadata,
        )
        db.add(record)
        created.append(record)

    if created:
        await db.commit()
        for r in created:
            await db.refresh(r)

    return created


# ────────────────────────────────────────────────────────────────
# 建议应用 — 将 proposed_value 写入 Agent 配置
# ────────────────────────────────────────────────────────────────


async def apply_proposal_to_agent(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> EvolutionProposalRecord:
    """将进化建议应用到 Agent 配置。

    流程：
    1. 校验状态为 approved（或 pending → auto-apply 场景先推进到 approved）
    2. 查找目标 Agent
    3. 创建版本快照（修改前）
    4. 根据 proposal_type 修改 Agent 对应字段
    5. 推进状态到 applied

    Raises:
        NotFoundError: Agent 不存在
        ValidationError: 状态不允许
    """
    from app.models.agent import AgentConfig

    record = await get_proposal(db, proposal_id)

    # 如果是 pending 状态（auto-apply 场景），先推进到 approved
    if record.status == "pending":
        record.status = "approved"

    if record.status != "approved":
        raise ValidationError(
            f"只能应用 approved 状态的建议，当前状态: '{record.status}'"
        )

    # 查找目标 Agent
    stmt = select(AgentConfig).where(AgentConfig.name == record.agent_name)
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent '{record.agent_name}' 不存在")

    # 创建版本快照（修改前）
    await _create_version_snapshot(
        db, agent, f"进化应用: {record.trigger_reason[:200]}"
    )

    # 应用 proposed_value 到 Agent 配置
    proposed = record.proposed_value or {}
    _apply_value_to_agent(agent, record.proposal_type, proposed)

    # 推进状态
    record.status = "applied"
    record.applied_at = datetime.now(timezone.utc)
    record.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(record)
    return record


def _apply_value_to_agent(
    agent: object,
    proposal_type: str,
    proposed: dict,
) -> None:
    """根据建议类型将 proposed_value 写入 Agent 对应字段。"""
    if proposal_type == "instructions":
        if "instructions" in proposed:
            agent.instructions = proposed["instructions"]  # type: ignore[attr-defined]
    elif proposal_type == "model":
        if "model" in proposed:
            agent.model = proposed["model"]  # type: ignore[attr-defined]
    elif proposal_type == "tools":
        if "tool_names" in proposed:
            agent.tool_names = proposed["tool_names"]  # type: ignore[attr-defined]
    elif proposal_type == "guardrails":
        if "guardrail_ids" in proposed:
            agent.guardrail_ids = proposed["guardrail_ids"]  # type: ignore[attr-defined]


async def _create_version_snapshot(
    db: AsyncSession,
    agent: object,
    change_summary: str,
) -> None:
    """创建 Agent 版本快照。"""
    from app.models.agent_version import AgentConfigVersion

    # 获取当前最大版本号
    from sqlalchemy import func as sa_func

    agent_id = getattr(agent, "id")
    max_q = select(sa_func.max(AgentConfigVersion.version)).where(
        AgentConfigVersion.agent_config_id == agent_id
    )
    max_ver = (await db.execute(max_q)).scalar() or 0

    # 构建快照 JSON
    snapshot = {
        "name": getattr(agent, "name", ""),
        "model": getattr(agent, "model", ""),
        "instructions": getattr(agent, "instructions", ""),
    }

    version = AgentConfigVersion(
        agent_config_id=agent_id,
        version=max_ver + 1,
        snapshot=snapshot,
        change_summary=change_summary,
    )
    db.add(version)
