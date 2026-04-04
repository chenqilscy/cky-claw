"""Agent 评估与反馈 API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.schemas.evaluation import (
    AgentQualitySummary,
    RunEvaluationCreate,
    RunEvaluationListResponse,
    RunEvaluationResponse,
    RunFeedbackCreate,
    RunFeedbackListResponse,
    RunFeedbackResponse,
)
from app.services import evaluation as svc

router = APIRouter(prefix="/api/v1/evaluations", tags=["评估"])


# ── 评估 ──────────────────────────────────────────


@router.get("", response_model=RunEvaluationListResponse)
async def list_evaluations(
    agent_id: uuid.UUID | None = None,
    run_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> RunEvaluationListResponse:
    """查询评估列表。"""
    items, total = await svc.list_evaluations(db, agent_id=agent_id, run_id=run_id, limit=limit, offset=offset)
    return RunEvaluationListResponse(
        data=[RunEvaluationResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RunEvaluationResponse, status_code=201)
async def create_evaluation(
    data: RunEvaluationCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> RunEvaluationResponse:
    """创建运行评估。"""
    record = await svc.create_evaluation(db, data)
    return RunEvaluationResponse.model_validate(record)


@router.get("/{eval_id}", response_model=RunEvaluationResponse)
async def get_evaluation(
    eval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> RunEvaluationResponse:
    """获取单个评估。"""
    record = await svc.get_evaluation(db, eval_id)
    if record is None:
        raise HTTPException(404, "evaluation not found")
    return RunEvaluationResponse.model_validate(record)


# ── Agent 质量汇总 ─────────────────────────────────


@router.get("/agents/{agent_id}/quality", response_model=AgentQualitySummary)
async def get_agent_quality(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> AgentQualitySummary:
    """获取 Agent 多维质量汇总。"""
    return await svc.get_agent_quality_summary(db, agent_id)


# ── 反馈 ──────────────────────────────────────────


@router.get("/feedbacks", response_model=RunFeedbackListResponse)
async def list_feedbacks(
    run_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> RunFeedbackListResponse:
    """查询反馈列表。"""
    items, total = await svc.list_feedbacks(db, run_id=run_id, limit=limit, offset=offset)
    return RunFeedbackListResponse(
        data=[RunFeedbackResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/feedbacks", response_model=RunFeedbackResponse, status_code=201)
async def create_feedback(
    data: RunFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> RunFeedbackResponse:
    """创建用户反馈。"""
    user_id = user.get("user_id")
    record = await svc.create_feedback(db, data, user_id=uuid.UUID(user_id) if user_id else None)
    return RunFeedbackResponse.model_validate(record)
