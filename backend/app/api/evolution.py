"""进化建议 API。"""

from __future__ import annotations

from typing import Any

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.evolution import (
    EvolutionProposalCreate,
    EvolutionProposalListResponse,
    EvolutionProposalResponse,
    EvolutionProposalUpdate,
)
from app.services import evolution as svc

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
