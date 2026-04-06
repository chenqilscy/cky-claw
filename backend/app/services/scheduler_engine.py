"""定时任务执行引擎 — 后台轮询 + 任务执行。"""

from __future__ import annotations

from typing import Any

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.scheduled_run import ScheduledRun
from app.models.scheduled_task import ScheduledTask

logger = logging.getLogger(__name__)

# 轮询间隔（秒）
POLL_INTERVAL = 30


async def execute_task(db: AsyncSession, task: ScheduledTask, triggered_by: str = "scheduler") -> ScheduledRun:
    """执行单个定时任务，创建执行记录。

    Args:
        db: 数据库会话
        task: 待执行的定时任务
        triggered_by: 触发方式（scheduler / manual）

    Returns:
        执行记录
    """
    run = ScheduledRun(
        task_id=task.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        triggered_by=triggered_by,
    )
    db.add(run)
    await db.flush()

    try:
        if task.task_type == "evolution_analyze":
            # 进化分析任务：读取信号 → 策略引擎生成建议
            output = await _execute_evolution_analyze(db, task)
        else:
            # 默认 agent_run 类型
            output = await _execute_agent_run(db, task)

        now = datetime.now(timezone.utc)
        run.status = "success"
        run.output = output
        run.finished_at = now
        run.duration_ms = (now - run.started_at).total_seconds() * 1000 if run.started_at else 0

    except Exception as exc:
        now = datetime.now(timezone.utc)
        run.status = "failed"
        run.error = str(exc)[:2000]
        run.finished_at = now
        run.duration_ms = (now - run.started_at).total_seconds() * 1000 if run.started_at else 0
        logger.exception("定时任务 %s 执行失败", task.id)

    # 更新任务的执行时间
    task.last_run_at = datetime.now(timezone.utc)
    cron = croniter(task.cron_expr, task.last_run_at)
    task.next_run_at = cron.get_next(datetime)

    await db.commit()
    await db.refresh(run)
    return run


async def _execute_agent_run(db: AsyncSession, task: ScheduledTask) -> str:
    """执行 agent_run 类型的定时任务。"""
    from sqlalchemy import select as sa_select
    from app.models.agent import AgentConfig

    result = await db.execute(
        sa_select(AgentConfig).where(AgentConfig.id == task.agent_id)
    )
    agent_config = result.scalar_one_or_none()
    if agent_config is None:
        raise ValueError(f"Agent {task.agent_id} 不存在")

    return f"Agent '{agent_config.name}' 执行完成，输入: {task.input_text[:100]}"


async def _execute_evolution_analyze(db: AsyncSession, task: ScheduledTask) -> str:
    """执行 evolution_analyze 类型的定时任务。

    读取信号 → 策略引擎生成建议 → 可选自动应用。
    """
    from sqlalchemy import select as sa_select
    from app.models.agent import AgentConfig
    from app.services import evolution as evo_svc

    result = await db.execute(
        sa_select(AgentConfig).where(AgentConfig.id == task.agent_id)
    )
    agent_config = result.scalar_one_or_none()
    if agent_config is None:
        raise ValueError(f"Agent {task.agent_id} 不存在")

    proposals = await evo_svc.analyze_agent(db, agent_config.name)
    if not proposals:
        return f"Agent '{agent_config.name}' 进化分析完成，无新建议"

    # 检查是否启用自动应用（从 input_text 解析 JSON 配置）
    auto_apply = False
    min_confidence = 0.8
    try:
        import json
        meta = json.loads(task.input_text) if task.input_text else {}
        auto_apply = meta.get("auto_apply", False)
        min_confidence = meta.get("min_confidence", 0.8)
    except (json.JSONDecodeError, TypeError):
        pass

    applied_count = 0
    if auto_apply:
        for proposal in proposals:
            if proposal.confidence_score >= min_confidence:
                await evo_svc.apply_proposal_to_agent(db, proposal.id)
                applied_count += 1

    return (
        f"Agent '{agent_config.name}' 进化分析完成，"
        f"生成 {len(proposals)} 条建议，自动应用 {applied_count} 条"
    )


async def poll_and_execute() -> int:
    """单次轮询：查询到期任务并执行。

    Returns:
        本轮执行的任务数量
    """
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ScheduledTask).where(
                ScheduledTask.is_enabled == True,  # noqa: E712
                ScheduledTask.is_deleted == False,  # noqa: E712
                ScheduledTask.next_run_at <= now,
            )
        )
        due_tasks = list(result.scalars().all())

        if not due_tasks:
            return 0

        logger.info("发现 %d 个到期任务", len(due_tasks))

        for task in due_tasks:
            try:
                await execute_task(db, task)
            except Exception:
                logger.exception("任务 %s 执行异常", task.id)

        return len(due_tasks)


async def list_runs(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ScheduledRun], int]:
    """查询指定任务的执行历史。"""
    base = select(ScheduledRun).where(ScheduledRun.task_id == task_id)
    count_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(count_q) or 0

    result = await db.execute(
        base.order_by(ScheduledRun.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> ScheduledRun | None:
    """按 ID 获取执行记录。"""
    result = await db.execute(
        select(ScheduledRun).where(ScheduledRun.id == run_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 后台调度器（生命周期管理）
# ---------------------------------------------------------------------------

_scheduler_task: asyncio.Task[Any] | None = None


async def _scheduler_loop() -> None:
    """后台轮询循环。"""
    logger.info("定时任务调度器已启动，轮询间隔 %ds", POLL_INTERVAL)
    while True:
        try:
            count = await poll_and_execute()
            if count > 0:
                logger.info("本轮执行了 %d 个任务", count)
        except Exception:
            logger.exception("调度器轮询异常")
        await asyncio.sleep(POLL_INTERVAL)


def start_scheduler() -> None:
    """启动后台调度器（非阻塞）。"""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.warning("调度器已在运行")
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("定时任务调度器已创建")


def stop_scheduler() -> None:
    """停止后台调度器。"""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("定时任务调度器已停止")
    _scheduler_task = None
