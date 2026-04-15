"""进化建议 & 信号 API。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.evolution import (
    EvolutionAnalyzeResponse,
    EvolutionProposalCreate,
    EvolutionProposalListResponse,
    EvolutionProposalResponse,
    EvolutionProposalUpdate,
    EvolutionSignalCreate,
    EvolutionSignalListResponse,
    EvolutionSignalResponse,
    RollbackCheckRequest,
    RollbackCheckResponse,
    ScanRollbackResponse,
)
from app.services import evolution as svc

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/evolution", tags=["进化"])


@router.get("/proposals", response_model=EvolutionProposalListResponse)
async def list_proposals(
    agent_name: str | None = None,
    proposal_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionProposalListResponse:
    """获取进化建议列表。"""
    items, total = await svc.list_proposals(
        db,
        agent_name=agent_name,
        proposal_type=proposal_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return EvolutionProposalListResponse(
        data=[EvolutionProposalResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/proposals", response_model=EvolutionProposalResponse, status_code=201)
async def create_proposal(
    data: EvolutionProposalCreate,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionProposalResponse:
    """创建进化建议。"""
    record = await svc.create_proposal(db, data)
    return EvolutionProposalResponse.model_validate(record)


@router.get("/proposals/{proposal_id}", response_model=EvolutionProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionProposalResponse:
    """获取单个进化建议。"""
    record = await svc.get_proposal(db, proposal_id)
    return EvolutionProposalResponse.model_validate(record)


@router.patch("/proposals/{proposal_id}", response_model=EvolutionProposalResponse)
async def update_proposal(
    proposal_id: uuid.UUID,
    data: EvolutionProposalUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionProposalResponse:
    """更新进化建议（状态变更 + 评分更新）。"""
    record = await svc.update_proposal(db, proposal_id, data)
    return EvolutionProposalResponse.model_validate(record)


@router.delete("/proposals/{proposal_id}", status_code=204)
async def delete_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> None:
    """删除进化建议。"""
    await svc.delete_proposal(db, proposal_id)


# ────────────────────────────────────────────────────────────────
# 信号 API
# ────────────────────────────────────────────────────────────────


@router.post("/signals", response_model=EvolutionSignalResponse, status_code=201)
async def create_signal(
    data: EvolutionSignalCreate,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionSignalResponse:
    """上报一条进化信号。"""
    record = await svc.create_signal(db, data)
    return EvolutionSignalResponse.model_validate(record)


@router.post(
    "/signals/batch",
    response_model=list[EvolutionSignalResponse],
    status_code=201,
)
async def create_signals_batch(
    signals: list[EvolutionSignalCreate],
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> list[EvolutionSignalResponse]:
    """批量上报进化信号。"""
    records = await svc.create_signals_batch(db, signals)
    return [EvolutionSignalResponse.model_validate(r) for r in records]


@router.get("/signals", response_model=EvolutionSignalListResponse)
async def list_signals(
    agent_name: str | None = None,
    signal_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionSignalListResponse:
    """获取进化信号列表。"""
    items, total = await svc.list_signals(
        db,
        agent_name=agent_name,
        signal_type=signal_type,
        limit=limit,
        offset=offset,
    )
    return EvolutionSignalListResponse(
        data=[EvolutionSignalResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ────────────────────────────────────────────────────────────────
# 策略分析 API
# ────────────────────────────────────────────────────────────────


@router.post("/analyze/{agent_name}", response_model=EvolutionAnalyzeResponse)
async def analyze_agent(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> EvolutionAnalyzeResponse:
    """对指定 Agent 执行策略分析，生成优化建议。"""
    proposals = await svc.analyze_agent(db, agent_name)
    return EvolutionAnalyzeResponse(
        proposals_created=len(proposals),
        proposals=[EvolutionProposalResponse.model_validate(p) for p in proposals],
    )


# ────────────────────────────────────────────────────────────────
# S5: 自动回滚监控 API
# ────────────────────────────────────────────────────────────────


@router.post(
    "/proposals/{proposal_id}/rollback-check",
    response_model=RollbackCheckResponse,
)
async def rollback_check(
    proposal_id: uuid.UUID,
    data: RollbackCheckRequest,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> RollbackCheckResponse:
    """检查已应用建议是否需要回滚。

    当 eval_after 相比 eval_before 下降超过 rollback_threshold 时自动回滚。
    """
    triggered, record = await svc.check_and_rollback(
        db,
        proposal_id,
        data.eval_after,
        rollback_threshold=data.rollback_threshold,
    )
    return RollbackCheckResponse(
        rolled_back=triggered,
        proposal=EvolutionProposalResponse.model_validate(record),
    )


@router.post("/scan-rollback", response_model=ScanRollbackResponse)
async def scan_rollback(
    rollback_threshold: float = 0.1,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> ScanRollbackResponse:
    """扫描所有已应用建议，对评分退化超过阈值的自动回滚。"""
    rolled_back = await svc.scan_and_rollback_all(
        db, rollback_threshold=rollback_threshold
    )
    return ScanRollbackResponse(
        rolled_back_count=len(rolled_back),
        proposals=[EvolutionProposalResponse.model_validate(r) for r in rolled_back],
    )
