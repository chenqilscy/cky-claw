"""Benchmark 评测业务逻辑层。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.benchmark import BenchmarkRun, BenchmarkSuite


# ─── Suite CRUD ───

async def create_suite(
    db: AsyncSession,
    *,
    name: str,
    description: str = "",
    agent_name: str = "",
    model: str = "",
    config: dict | None = None,
    tags: list[str] | None = None,
    created_by: uuid.UUID | None = None,
) -> BenchmarkSuite:
    """创建评测套件。"""
    suite = BenchmarkSuite(
        name=name,
        description=description,
        agent_name=agent_name,
        model=model,
        config=config,
        tags=tags,
        created_by=created_by,
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return suite


async def list_suites(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BenchmarkSuite], int]:
    """查询套件列表。"""
    base = select(BenchmarkSuite).where(BenchmarkSuite.is_deleted == False)  # noqa: E712
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.scalars(
        base.order_by(BenchmarkSuite.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows.all()), total or 0


async def get_suite(db: AsyncSession, suite_id: uuid.UUID) -> BenchmarkSuite:
    """获取单个套件。"""
    suite = await db.get(BenchmarkSuite, suite_id)
    if not suite or suite.is_deleted:
        raise NotFoundError(f"Benchmark suite {suite_id} not found")
    return suite


async def update_suite(
    db: AsyncSession,
    suite_id: uuid.UUID,
    **kwargs: object,
) -> BenchmarkSuite:
    """更新套件。"""
    suite = await get_suite(db, suite_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(suite, k, v)
    suite.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(suite)
    return suite


async def delete_suite(db: AsyncSession, suite_id: uuid.UUID) -> None:
    """软删除套件。"""
    suite = await get_suite(db, suite_id)
    suite.is_deleted = True
    suite.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Run CRUD ───

async def create_run(
    db: AsyncSession,
    *,
    suite_id: uuid.UUID,
) -> BenchmarkRun:
    """创建评测运行。"""
    # 确保 suite 存在
    await get_suite(db, suite_id)
    run = BenchmarkRun(
        suite_id=suite_id,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def list_runs(
    db: AsyncSession,
    *,
    suite_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BenchmarkRun], int]:
    """查询运行列表。"""
    base = select(BenchmarkRun).where(BenchmarkRun.is_deleted == False)  # noqa: E712
    if suite_id:
        base = base.where(BenchmarkRun.suite_id == suite_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.scalars(
        base.order_by(BenchmarkRun.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows.all()), total or 0


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> BenchmarkRun:
    """获取单个运行。"""
    run = await db.get(BenchmarkRun, run_id)
    if not run or run.is_deleted:
        raise NotFoundError(f"Benchmark run {run_id} not found")
    return run


async def update_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    **kwargs: object,
) -> BenchmarkRun:
    """更新运行结果。"""
    run = await get_run(db, run_id)
    for k, v in kwargs.items():
        if v is not None:
            setattr(run, k, v)
    run.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def complete_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    *,
    total_cases: int,
    passed_cases: int,
    failed_cases: int,
    error_cases: int,
    overall_score: float,
    pass_rate: float,
    total_latency_ms: float,
    total_tokens: int,
    dimension_summaries: dict | None = None,
    report: dict | None = None,
) -> BenchmarkRun:
    """完成评测运行，填充结果。"""
    run = await get_run(db, run_id)
    run.status = "completed"
    run.total_cases = total_cases
    run.passed_cases = passed_cases
    run.failed_cases = failed_cases
    run.error_cases = error_cases
    run.overall_score = overall_score
    run.pass_rate = pass_rate
    run.total_latency_ms = total_latency_ms
    run.total_tokens = total_tokens
    run.dimension_summaries = dimension_summaries
    run.report = report
    run.finished_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


# ─── Dashboard ───

async def get_dashboard(db: AsyncSession) -> dict:
    """获取 Benchmark 仪表盘汇总。"""
    suite_count = await db.scalar(
        select(func.count()).select_from(
            select(BenchmarkSuite).where(BenchmarkSuite.is_deleted == False).subquery()  # noqa: E712
        )
    ) or 0

    run_base = select(BenchmarkRun).where(BenchmarkRun.is_deleted == False)  # noqa: E712
    run_count = await db.scalar(
        select(func.count()).select_from(run_base.subquery())
    ) or 0

    completed_base = run_base.where(BenchmarkRun.status == "completed")
    completed_count = await db.scalar(
        select(func.count()).select_from(completed_base.subquery())
    ) or 0

    avg_score = await db.scalar(
        select(func.avg(BenchmarkRun.overall_score)).where(
            BenchmarkRun.is_deleted == False,  # noqa: E712
            BenchmarkRun.status == "completed",
        )
    ) or 0.0

    avg_pass = await db.scalar(
        select(func.avg(BenchmarkRun.pass_rate)).where(
            BenchmarkRun.is_deleted == False,  # noqa: E712
            BenchmarkRun.status == "completed",
        )
    ) or 0.0

    return {
        "total_suites": suite_count,
        "total_runs": run_count,
        "completed_runs": completed_count,
        "avg_score": round(float(avg_score), 4),
        "avg_pass_rate": round(float(avg_pass), 4),
    }
