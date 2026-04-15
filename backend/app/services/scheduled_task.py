"""ScheduledTask 服务 — 定时任务 CRUD。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from croniter import croniter
from sqlalchemy import func, select

from app.models.scheduled_task import ScheduledTask

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.scheduled_task import ScheduledTaskCreate, ScheduledTaskUpdate


async def list_scheduled_tasks(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    is_enabled: bool | None = None,
    org_id: uuid.UUID | None = None,
) -> tuple[list[ScheduledTask], int]:
    """分页获取定时任务列表。"""
    query = select(ScheduledTask).where(ScheduledTask.is_deleted == False)  # noqa: E712

    if is_enabled is not None:
        query = query.where(ScheduledTask.is_enabled == is_enabled)
    if org_id is not None:
        query = query.where(ScheduledTask.org_id == org_id)

    count_query = select(func.count()).select_from(query.subquery())
    query = query.order_by(ScheduledTask.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    items = list(result.scalars().all())
    total = await db.scalar(count_query) or 0
    return items, total


async def get_scheduled_task(db: AsyncSession, task_id: uuid.UUID) -> ScheduledTask | None:
    """按 ID 获取定时任务。"""
    result = await db.execute(select(ScheduledTask).where(
        ScheduledTask.id == task_id, ScheduledTask.is_deleted == False  # noqa: E712
    ))
    return result.scalar_one_or_none()


async def create_scheduled_task(
    db: AsyncSession,
    data: ScheduledTaskCreate,
) -> ScheduledTask:
    """创建定时任务。"""
    now = datetime.now(UTC)
    cron = croniter(data.cron_expr, now)
    next_run = cron.get_next(datetime)

    task = ScheduledTask(
        name=data.name,
        description=data.description,
        agent_id=data.agent_id,
        cron_expr=data.cron_expr,
        input_text=data.input_text,
        next_run_at=next_run,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_scheduled_task(
    db: AsyncSession,
    task: ScheduledTask,
    data: ScheduledTaskUpdate,
) -> ScheduledTask:
    """更新定时任务。"""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    # 如果 cron 表达式变更，重新计算 next_run_at
    if "cron_expr" in update_data:
        now = datetime.now(UTC)
        cron = croniter(task.cron_expr, now)
        task.next_run_at = cron.get_next(datetime)

    await db.commit()
    await db.refresh(task)
    return task


async def delete_scheduled_task(db: AsyncSession, task: ScheduledTask) -> None:
    """软删除定时任务。"""
    task.is_deleted = True
    task.deleted_at = datetime.now(UTC)
    await db.commit()


async def get_due_tasks(db: AsyncSession) -> list[ScheduledTask]:
    """获取到期需要执行的任务列表。"""
    now = datetime.now(UTC)
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.is_enabled == True,  # noqa: E712
            ScheduledTask.is_deleted == False,  # noqa: E712
            ScheduledTask.next_run_at <= now,
        )
    )
    return list(result.scalars().all())


async def mark_task_executed(db: AsyncSession, task: ScheduledTask) -> None:
    """标记任务已执行，更新 last_run_at 和 next_run_at。"""
    now = datetime.now(UTC)
    task.last_run_at = now
    cron = croniter(task.cron_expr, now)
    task.next_run_at = cron.get_next(datetime)
    await db.commit()
