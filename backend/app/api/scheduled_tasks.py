"""定时任务 API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskListResponse,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from app.services import scheduled_task as svc

router = APIRouter(prefix="/api/v1/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("", response_model=ScheduledTaskListResponse, dependencies=[Depends(require_admin)])
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScheduledTaskListResponse:
    items, total = await svc.list_scheduled_tasks(db, limit=limit, offset=offset, is_enabled=is_enabled)
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


@router.post("", response_model=ScheduledTaskResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_task(
    data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_db),
) -> ScheduledTaskResponse:
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
