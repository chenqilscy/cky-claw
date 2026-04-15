"""Benchmark 评测 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.schemas.benchmark import (
    BenchmarkDashboard,
    BenchmarkRunCreate,
    BenchmarkRunListResponse,
    BenchmarkRunResponse,
    BenchmarkRunUpdate,
    BenchmarkSuiteCreate,
    BenchmarkSuiteListResponse,
    BenchmarkSuiteResponse,
    BenchmarkSuiteUpdate,
)
from app.services import benchmark as bench_svc

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])


# ─── Dashboard ───

@router.get(
    "/dashboard",
    response_model=BenchmarkDashboard,
    dependencies=[Depends(require_permission("benchmark", "read"))],
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
) -> BenchmarkDashboard:
    """获取 Benchmark 仪表盘汇总。"""
    data = await bench_svc.get_dashboard(db)
    return BenchmarkDashboard(**data)


# ─── Suite CRUD ───

@router.post(
    "/suites",
    response_model=BenchmarkSuiteResponse,
    status_code=201,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def create_suite(
    body: BenchmarkSuiteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BenchmarkSuiteResponse:
    """创建评测套件。"""
    suite = await bench_svc.create_suite(
        db,
        name=body.name,
        description=body.description,
        agent_name=body.agent_name,
        model=body.model,
        config=body.config,
        tags=body.tags,
        created_by=user.id,
    )
    return BenchmarkSuiteResponse.model_validate(suite)


@router.get(
    "/suites",
    response_model=BenchmarkSuiteListResponse,
    dependencies=[Depends(require_permission("benchmark", "read"))],
)
async def list_suites(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteListResponse:
    """查询评测套件列表。"""
    rows, total = await bench_svc.list_suites(db, limit=limit, offset=offset)
    return BenchmarkSuiteListResponse(
        data=[BenchmarkSuiteResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.get(
    "/suites/{suite_id}",
    response_model=BenchmarkSuiteResponse,
    dependencies=[Depends(require_permission("benchmark", "read"))],
)
async def get_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteResponse:
    """获取套件详情。"""
    suite = await bench_svc.get_suite(db, suite_id)
    return BenchmarkSuiteResponse.model_validate(suite)


@router.put(
    "/suites/{suite_id}",
    response_model=BenchmarkSuiteResponse,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def update_suite(
    suite_id: uuid.UUID,
    body: BenchmarkSuiteUpdate,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteResponse:
    """更新评测套件。"""
    suite = await bench_svc.update_suite(
        db,
        suite_id,
        **body.model_dump(exclude_unset=True),
    )
    return BenchmarkSuiteResponse.model_validate(suite)


@router.delete(
    "/suites/{suite_id}",
    status_code=204,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def delete_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除评测套件。"""
    await bench_svc.delete_suite(db, suite_id)


# ─── Run CRUD ───

@router.post(
    "/runs",
    response_model=BenchmarkRunResponse,
    status_code=201,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def create_run(
    body: BenchmarkRunCreate,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunResponse:
    """创建评测运行。"""
    run = await bench_svc.create_run(db, suite_id=body.suite_id)
    return BenchmarkRunResponse.model_validate(run)


@router.get(
    "/runs",
    response_model=BenchmarkRunListResponse,
    dependencies=[Depends(require_permission("benchmark", "read"))],
)
async def list_runs(
    suite_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunListResponse:
    """查询评测运行列表。"""
    rows, total = await bench_svc.list_runs(
        db, suite_id=suite_id, limit=limit, offset=offset
    )
    return BenchmarkRunListResponse(
        data=[BenchmarkRunResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.get(
    "/runs/{run_id}",
    response_model=BenchmarkRunResponse,
    dependencies=[Depends(require_permission("benchmark", "read"))],
)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunResponse:
    """获取运行详情。"""
    run = await bench_svc.get_run(db, run_id)
    return BenchmarkRunResponse.model_validate(run)


@router.put(
    "/runs/{run_id}",
    response_model=BenchmarkRunResponse,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def update_run(
    run_id: uuid.UUID,
    body: BenchmarkRunUpdate,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunResponse:
    """更新运行结果。"""
    run = await bench_svc.update_run(
        db,
        run_id,
        **body.model_dump(exclude_unset=True),
    )
    return BenchmarkRunResponse.model_validate(run)


@router.post(
    "/runs/{run_id}/complete",
    response_model=BenchmarkRunResponse,
    dependencies=[Depends(require_permission("benchmark", "write"))],
)
async def complete_run(
    run_id: uuid.UUID,
    body: BenchmarkRunUpdate,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunResponse:
    """完成运行并提交结果。"""
    run = await bench_svc.complete_run(
        db,
        run_id,
        total_cases=body.total_cases or 0,
        passed_cases=body.passed_cases or 0,
        failed_cases=body.failed_cases or 0,
        error_cases=body.error_cases or 0,
        overall_score=body.overall_score or 0.0,
        pass_rate=body.pass_rate or 0.0,
        total_latency_ms=body.total_latency_ms or 0.0,
        total_tokens=body.total_tokens or 0,
        dimension_summaries=body.dimension_summaries,
        report=body.report,
    )
    return BenchmarkRunResponse.model_validate(run)
