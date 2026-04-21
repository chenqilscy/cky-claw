"""定时任务 API。"""

from __future__ import annotations
import uuid

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.tenant import check_quota, get_org_id
from app.schemas.scheduled_task import (
    ScheduledRunListResponse,
    ScheduledRunResponse,
    ScheduledTaskCreate,
    ScheduledTaskListResponse,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from app.services import scheduled_task as svc
from app.services import scheduler_engine

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("", response_model=ScheduledTaskListResponse, dependencies=[Depends(require_admin)])
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ScheduledTaskListResponse:
    items, total = await svc.list_scheduled_tasks(db, limit=limit, offset=offset, is_enabled=is_enabled, org_id=org_id)
    return ScheduledTaskListResponse(
        data=[ScheduledTaskResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get("/{task_id}", response_model=ScheduledTaskResponse, dependencies=[Depends(require_admin)])
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledTaskResponse:
    task = await svc.get_scheduled_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时任务不存在")
    return ScheduledTaskResponse.model_validate(task)


@router.post(
    "",
    response_model=ScheduledTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_task(
    data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> ScheduledTaskResponse:
    await check_quota(db, org_id, "max_scheduled_tasks")
    task = await svc.create_scheduled_task(db, data)
    return ScheduledTaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=ScheduledTaskResponse, dependencies=[Depends(require_admin)])
async def update_task(
    task_id: uuid.UUID,
    data: ScheduledTaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScheduledTaskResponse:
    task = await svc.get_scheduled_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时任务不存在")
    task = await svc.update_scheduled_task(db, task, data)
    return ScheduledTaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await svc.get_scheduled_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时任务不存在")
    await svc.delete_scheduled_task(db, task)


# ---------------------------------------------------------------------------
# 执行历史 & 手动触发
# ---------------------------------------------------------------------------


@router.post(
    "/{task_id}/execute",
    response_model=ScheduledRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def execute_task_now(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledRunResponse:
    """手动触发一次定时任务执行。"""
    task = await svc.get_scheduled_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时任务不存在")
    run = await scheduler_engine.execute_task(db, task, triggered_by="manual")
    return ScheduledRunResponse.model_validate(run)


@router.get(
    "/{task_id}/runs",
    response_model=ScheduledRunListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_task_runs(
    task_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ScheduledRunListResponse:
    """查询任务执行历史。"""
    task = await svc.get_scheduled_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时任务不存在")
    runs, total = await scheduler_engine.list_runs(db, task_id, limit=limit, offset=offset)
    return ScheduledRunListResponse(
        data=[ScheduledRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get(
    "/{task_id}/runs/{run_id}",
    response_model=ScheduledRunResponse,
    dependencies=[Depends(require_admin)],
)
async def get_task_run(
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledRunResponse:
    """获取单次执行记录详情。"""
    run = await scheduler_engine.get_run(db, run_id)
    if run is None or run.task_id != task_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    return ScheduledRunResponse.model_validate(run)
