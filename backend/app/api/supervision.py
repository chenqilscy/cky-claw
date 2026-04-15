"""监督面板 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.supervision import (
    PauseRequest,
    ResumeRequest,
    SupervisionActionResponse,
    SupervisionSessionDetail,
    SupervisionSessionListResponse,
)
from app.services import supervision as supervision_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/v1/supervision",
    tags=["supervision"],
    dependencies=[Depends(require_admin)],
)


@router.get("/sessions", response_model=SupervisionSessionListResponse)
async def list_active_sessions(
    agent_name: str | None = Query(None, description="按 Agent 名称筛选"),
    status: str | None = Query(None, description="按状态筛选: active / paused / completed"),
    db: AsyncSession = Depends(get_db),
) -> SupervisionSessionListResponse:
    """获取活跃会话列表（含 Token 统计）。"""
    return await supervision_service.list_active_sessions(
        db, agent_name=agent_name, status=status
    )


@router.get("/sessions/{session_id}", response_model=SupervisionSessionDetail)
async def get_session_detail(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SupervisionSessionDetail:
    """获取会话详情（含消息历史）。"""
    return await supervision_service.get_session_detail(db, session_id)


@router.post("/sessions/{session_id}/pause", response_model=SupervisionActionResponse)
async def pause_session(
    session_id: uuid.UUID,
    data: PauseRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> SupervisionActionResponse:
    """暂停会话。"""
    reason = data.reason if data else ""
    return await supervision_service.pause_session(db, session_id, reason=reason)


@router.post("/sessions/{session_id}/resume", response_model=SupervisionActionResponse)
async def resume_session(
    session_id: uuid.UUID,
    data: ResumeRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> SupervisionActionResponse:
    """恢复会话。"""
    instructions = data.injected_instructions if data else ""
    return await supervision_service.resume_session(db, session_id, injected_instructions=instructions)
