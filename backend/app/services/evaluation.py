"""Agent 评估业务逻辑。"""

from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import RunEvaluation, RunFeedback
from app.schemas.evaluation import AgentQualitySummary, RunEvaluationCreate, RunFeedbackCreate

_DIMENSION_WEIGHTS = {
    "accuracy": 0.2,
    "relevance": 0.15,
    "coherence": 0.1,
    "helpfulness": 0.2,
    "safety": 0.15,
    "efficiency": 0.1,
    "tool_usage": 0.1,
}


def _calc_overall(data: RunEvaluationCreate) -> float:
    """加权计算综合分。"""
    return round(
        data.accuracy * _DIMENSION_WEIGHTS["accuracy"]
        + data.relevance * _DIMENSION_WEIGHTS["relevance"]
        + data.coherence * _DIMENSION_WEIGHTS["coherence"]
        + data.helpfulness * _DIMENSION_WEIGHTS["helpfulness"]
        + data.safety * _DIMENSION_WEIGHTS["safety"]
        + data.efficiency * _DIMENSION_WEIGHTS["efficiency"]
        + data.tool_usage * _DIMENSION_WEIGHTS["tool_usage"],
        4,
    )


# ── 评估 CRUD ─────────────────────────────────────


async def create_evaluation(db: AsyncSession, data: RunEvaluationCreate) -> RunEvaluation:
    """创建运行评估。"""
    overall = _calc_overall(data)
    record = RunEvaluation(
        run_id=data.run_id,
        agent_id=data.agent_id,
        accuracy=data.accuracy,
        relevance=data.relevance,
        coherence=data.coherence,
        helpfulness=data.helpfulness,
        safety=data.safety,
        efficiency=data.efficiency,
        tool_usage=data.tool_usage,
        overall_score=overall,
        eval_method=data.eval_method,
        evaluator=data.evaluator,
        comment=data.comment,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_evaluations(
    db: AsyncSession,
    *,
    agent_id: uuid.UUID | None = None,
    run_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[RunEvaluation], int]:
    """查询评估列表。"""
    q = select(RunEvaluation)
    count_q = select(func.count()).select_from(RunEvaluation)

    if agent_id is not None:
        q = q.where(RunEvaluation.agent_id == agent_id)
        count_q = count_q.where(RunEvaluation.agent_id == agent_id)
    if run_id is not None:
        q = q.where(RunEvaluation.run_id == run_id)
        count_q = count_q.where(RunEvaluation.run_id == run_id)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(q.order_by(RunEvaluation.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_evaluation(db: AsyncSession, eval_id: uuid.UUID) -> RunEvaluation | None:
    """获取单个评估。"""
    return await db.get(RunEvaluation, eval_id)


# ── 反馈 CRUD ─────────────────────────────────────


async def create_feedback(db: AsyncSession, data: RunFeedbackCreate, user_id: uuid.UUID | None = None) -> RunFeedback:
    """创建用户反馈。"""
    record = RunFeedback(
        run_id=data.run_id,
        user_id=user_id,
        rating=data.rating,
        comment=data.comment,
        tags=data.tags,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_feedbacks(
    db: AsyncSession,
    *,
    run_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[RunFeedback], int]:
    """查询反馈列表。"""
    q = select(RunFeedback)
    count_q = select(func.count()).select_from(RunFeedback)

    if run_id is not None:
        q = q.where(RunFeedback.run_id == run_id)
        count_q = count_q.where(RunFeedback.run_id == run_id)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(q.order_by(RunFeedback.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


# ── Agent 质量汇总 ─────────────────────────────────


async def get_agent_quality_summary(db: AsyncSession, agent_id: uuid.UUID) -> AgentQualitySummary:
    """获取 Agent 多维质量汇总。"""
    # 评估汇总
    eval_q = select(
        func.count().label("eval_count"),
        func.avg(RunEvaluation.accuracy).label("avg_accuracy"),
        func.avg(RunEvaluation.relevance).label("avg_relevance"),
        func.avg(RunEvaluation.coherence).label("avg_coherence"),
        func.avg(RunEvaluation.helpfulness).label("avg_helpfulness"),
        func.avg(RunEvaluation.safety).label("avg_safety"),
        func.avg(RunEvaluation.efficiency).label("avg_efficiency"),
        func.avg(RunEvaluation.tool_usage).label("avg_tool_usage"),
        func.avg(RunEvaluation.overall_score).label("avg_overall"),
    ).where(RunEvaluation.agent_id == agent_id)

    eval_row = (await db.execute(eval_q)).one()

    # 反馈汇总 — 通过 run_id 关联 evaluation 找到 agent 的反馈
    feedback_q = select(
        func.count().label("total"),
        func.sum(case((RunFeedback.rating > 0, 1), else_=0)).label("positive"),
    ).where(
        RunFeedback.run_id.in_(
            select(RunEvaluation.run_id).where(RunEvaluation.agent_id == agent_id)
        )
    )
    feedback_row = (await db.execute(feedback_q)).one()

    fb_total = feedback_row.total or 0
    fb_positive = feedback_row.positive or 0

    return AgentQualitySummary(
        agent_id=agent_id,
        eval_count=eval_row.eval_count or 0,
        avg_accuracy=round(float(eval_row.avg_accuracy or 0), 4),
        avg_relevance=round(float(eval_row.avg_relevance or 0), 4),
        avg_coherence=round(float(eval_row.avg_coherence or 0), 4),
        avg_helpfulness=round(float(eval_row.avg_helpfulness or 0), 4),
        avg_safety=round(float(eval_row.avg_safety or 0), 4),
        avg_efficiency=round(float(eval_row.avg_efficiency or 0), 4),
        avg_tool_usage=round(float(eval_row.avg_tool_usage or 0), 4),
        avg_overall=round(float(eval_row.avg_overall or 0), 4),
        feedback_count=fb_total,
        positive_rate=round(fb_positive / fb_total, 4) if fb_total > 0 else 0.0,
    )
