"""Checkpoint 管理 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.deps import get_db, require_permission
from app.models.checkpoint import CheckpointRecord
from app.schemas.checkpoint import CheckpointListResponse, CheckpointResponse
from app.services.checkpoint_backend import PostgresCheckpointBackend

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/checkpoints", tags=["checkpoints"])


def _to_response(r: CheckpointRecord) -> CheckpointResponse:
    """将 ORM 记录转为响应模型。"""
    return CheckpointResponse(
        checkpoint_id=r.checkpoint_id,
        run_id=r.run_id,
        turn_count=r.turn_count,
        current_agent_name=r.current_agent_name,
        messages=r.messages or [],
        token_usage=r.token_usage or {},
        context=r.context or {},
        created_at=r.created_at,
    )


@router.get("", response_model=CheckpointListResponse)
async def list_checkpoints(
    run_id: str = Query(..., min_length=1, description="运行 ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: Any = Depends(require_permission("runs", "read")),
) -> CheckpointListResponse:
    """列出指定 run_id 的所有 checkpoint。"""
    base = select(CheckpointRecord).where(CheckpointRecord.run_id == run_id)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(CheckpointRecord.turn_count.asc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return CheckpointListResponse(
        data=[_to_response(r) for r in rows],
        total=total,
    )


@router.get("/latest", response_model=CheckpointResponse | None)
async def get_latest_checkpoint(
    run_id: str = Query(..., min_length=1, description="运行 ID"),
    db: AsyncSession = Depends(get_db),
    _user: Any = Depends(require_permission("runs", "read")),
) -> CheckpointResponse | None:
    """获取指定 run_id 的最新 checkpoint。"""
    backend = PostgresCheckpointBackend(db)
    cp = await backend.load_latest(run_id)
    if cp is None:
        return None
    # 从 backend 直接查单条 ORM 更高效，但复用 backend 保持一致
    stmt = (
        select(CheckpointRecord)
        .where(CheckpointRecord.checkpoint_id == cp.checkpoint_id)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return _to_response(row) if row else None


@router.delete("/{run_id}", status_code=204)
async def delete_checkpoints(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _user: Any = Depends(require_permission("runs", "write")),
) -> None:
    """删除指定 run_id 的全部 checkpoint。"""
    backend = PostgresCheckpointBackend(db)
    await backend.delete(run_id)
    await db.commit()
