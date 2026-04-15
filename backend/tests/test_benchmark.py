"""Benchmark 评测全栈测试 — Schema / API / Service / Router。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

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

now = datetime.now(UTC)
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_suite(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "accuracy-v1",
        "description": "Accuracy benchmark",
        "agent_name": "my-agent",
        "model": "gpt-4",
        "config": {"concurrency": 3},
        "tags": ["accuracy", "safety"],
        "created_by": USER_ID,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_run(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "suite_id": uuid.uuid4(),
        "status": "pending",
        "total_cases": 0,
        "passed_cases": 0,
        "failed_cases": 0,
        "error_cases": 0,
        "overall_score": 0.0,
        "pass_rate": 0.0,
        "total_latency_ms": 0.0,
        "total_tokens": 0,
        "dimension_summaries": None,
        "report": None,
        "started_at": now,
        "finished_at": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


# ─── Schema 测试 ───

class TestBenchmarkSchemas:
    """Schema 验证与序列化。"""

    def test_suite_create_valid(self) -> None:
        s = BenchmarkSuiteCreate(name="test-suite", agent_name="a", model="gpt-4")
        assert s.name == "test-suite"
        assert s.tags is None

    def test_suite_create_name_required(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkSuiteCreate()  # type: ignore[call-arg]

    def test_suite_update_partial(self) -> None:
        u = BenchmarkSuiteUpdate(name="new-name")
        dump = u.model_dump(exclude_unset=True)
        assert dump == {"name": "new-name"}

    def test_suite_response_from_orm(self) -> None:
        mock = _make_suite()
        resp = BenchmarkSuiteResponse.model_validate(mock)
        assert resp.name == "accuracy-v1"

    def test_suite_list_response(self) -> None:
        resp = BenchmarkSuiteListResponse(
            data=[BenchmarkSuiteResponse.model_validate(_make_suite())],
            total=1,
        )
        assert resp.total == 1
        assert len(resp.data) == 1

    def test_run_create_valid(self) -> None:
        sid = uuid.uuid4()
        r = BenchmarkRunCreate(suite_id=sid)
        assert r.suite_id == sid

    def test_run_update_status_validation(self) -> None:
        u = BenchmarkRunUpdate(status="completed")
        assert u.status == "completed"

    def test_run_update_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkRunUpdate(status="unknown")

    def test_run_response_from_orm(self) -> None:
        mock = _make_run(status="completed", overall_score=0.85, pass_rate=0.9)
        resp = BenchmarkRunResponse.model_validate(mock)
        assert resp.overall_score == 0.85

    def test_run_list_response(self) -> None:
        resp = BenchmarkRunListResponse(
            data=[BenchmarkRunResponse.model_validate(_make_run())],
            total=1,
        )
        assert resp.total == 1

    def test_dashboard_schema(self) -> None:
        d = BenchmarkDashboard(
            total_suites=5, total_runs=10, completed_runs=8, avg_score=0.78, avg_pass_rate=0.85
        )
        assert d.completed_runs == 8


# ─── API 测试 ───

SVC = "app.services.benchmark"


class TestBenchmarkSuiteAPI:
    """Suite CRUD API。"""

    def test_create_suite(self) -> None:
        from app.main import app

        mock_suite = _make_suite()
        with patch(f"{SVC}.create_suite", new_callable=AsyncMock, return_value=mock_suite):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/benchmark/suites",
                json={"name": "accuracy-v1", "agent_name": "my-agent", "model": "gpt-4"},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "accuracy-v1"

    def test_list_suites(self) -> None:
        from app.main import app

        mock_suite = _make_suite()
        with patch(f"{SVC}.list_suites", new_callable=AsyncMock, return_value=([mock_suite], 1)):
            client = TestClient(app)
            resp = client.get("/api/v1/benchmark/suites")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["data"]) == 1

    def test_get_suite(self) -> None:
        from app.main import app

        mock_suite = _make_suite()
        with patch(f"{SVC}.get_suite", new_callable=AsyncMock, return_value=mock_suite):
            client = TestClient(app)
            resp = client.get(f"/api/v1/benchmark/suites/{mock_suite.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "accuracy-v1"

    def test_update_suite(self) -> None:
        from app.main import app

        mock_suite = _make_suite(name="updated")
        with patch(f"{SVC}.update_suite", new_callable=AsyncMock, return_value=mock_suite):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/benchmark/suites/{mock_suite.id}",
                json={"name": "updated"},
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"

    def test_delete_suite(self) -> None:
        from app.main import app

        with patch(f"{SVC}.delete_suite", new_callable=AsyncMock):
            client = TestClient(app)
            resp = client.delete(f"/api/v1/benchmark/suites/{uuid.uuid4()}")
        assert resp.status_code == 204


class TestBenchmarkRunAPI:
    """Run CRUD API。"""

    def test_create_run(self) -> None:
        from app.main import app

        mock_run = _make_run()
        with patch(f"{SVC}.create_run", new_callable=AsyncMock, return_value=mock_run):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/benchmark/runs",
                json={"suite_id": str(mock_run.suite_id)},
            )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_list_runs(self) -> None:
        from app.main import app

        mock_run = _make_run()
        with patch(f"{SVC}.list_runs", new_callable=AsyncMock, return_value=([mock_run], 1)):
            client = TestClient(app)
            resp = client.get("/api/v1/benchmark/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    def test_list_runs_filter_suite(self) -> None:
        from app.main import app

        suite_id = uuid.uuid4()
        mock_run = _make_run(suite_id=suite_id)
        with patch(f"{SVC}.list_runs", new_callable=AsyncMock, return_value=([mock_run], 1)):
            client = TestClient(app)
            resp = client.get(f"/api/v1/benchmark/runs?suite_id={suite_id}")
        assert resp.status_code == 200

    def test_get_run(self) -> None:
        from app.main import app

        mock_run = _make_run()
        with patch(f"{SVC}.get_run", new_callable=AsyncMock, return_value=mock_run):
            client = TestClient(app)
            resp = client.get(f"/api/v1/benchmark/runs/{mock_run.id}")
        assert resp.status_code == 200

    def test_update_run(self) -> None:
        from app.main import app

        mock_run = _make_run(status="running")
        with patch(f"{SVC}.update_run", new_callable=AsyncMock, return_value=mock_run):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/benchmark/runs/{mock_run.id}",
                json={"status": "running"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_complete_run(self) -> None:
        from app.main import app

        mock_run = _make_run(
            status="completed",
            total_cases=10,
            passed_cases=8,
            failed_cases=1,
            error_cases=1,
            overall_score=0.85,
            pass_rate=0.8,
            total_latency_ms=12500.0,
            total_tokens=5000,
            finished_at=now,
        )
        with patch(f"{SVC}.complete_run", new_callable=AsyncMock, return_value=mock_run):
            client = TestClient(app)
            resp = client.post(
                f"/api/v1/benchmark/runs/{mock_run.id}/complete",
                json={
                    "total_cases": 10,
                    "passed_cases": 8,
                    "failed_cases": 1,
                    "error_cases": 1,
                    "overall_score": 0.85,
                    "pass_rate": 0.8,
                    "total_latency_ms": 12500.0,
                    "total_tokens": 5000,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["overall_score"] == 0.85


class TestBenchmarkDashboardAPI:
    """Dashboard API。"""

    def test_get_dashboard(self) -> None:
        from app.main import app

        mock_data = {
            "total_suites": 5,
            "total_runs": 10,
            "completed_runs": 8,
            "avg_score": 0.78,
            "avg_pass_rate": 0.85,
        }
        with patch(f"{SVC}.get_dashboard", new_callable=AsyncMock, return_value=mock_data):
            client = TestClient(app)
            resp = client.get("/api/v1/benchmark/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_suites"] == 5
        assert body["avg_score"] == 0.78


# ─── Service 测试 ───

class TestBenchmarkService:
    """Service 纯逻辑测试。"""

    @pytest.mark.asyncio
    async def test_create_suite_calls_db(self) -> None:
        from app.services.benchmark import create_suite

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        await create_suite(db, name="test")
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_suite_not_found(self) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.benchmark import get_suite

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await get_suite(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_delete_suite_soft(self) -> None:
        from app.services.benchmark import delete_suite

        mock_suite = MagicMock()
        mock_suite.is_deleted = False
        db = AsyncMock()
        db.get = AsyncMock(return_value=mock_suite)
        db.commit = AsyncMock()
        await delete_suite(db, uuid.uuid4())
        assert mock_suite.is_deleted is True

    @pytest.mark.asyncio
    async def test_create_run_checks_suite(self) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.benchmark import create_run

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await create_run(db, suite_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_complete_run_fills_fields(self) -> None:
        from app.services.benchmark import complete_run

        mock_run = MagicMock()
        mock_run.is_deleted = False
        db = AsyncMock()
        db.get = AsyncMock(return_value=mock_run)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        await complete_run(
            db,
            uuid.uuid4(),
            total_cases=5,
            passed_cases=4,
            failed_cases=1,
            error_cases=0,
            overall_score=0.9,
            pass_rate=0.8,
            total_latency_ms=3000.0,
            total_tokens=1000,
        )
        assert mock_run.status == "completed"
        assert mock_run.total_cases == 5
        assert mock_run.finished_at is not None


# ─── Router 注册测试 ───

class TestBenchmarkRouterRegistration:
    """验证路由注册。"""

    def test_benchmark_routes_exist(self) -> None:
        from app.main import app

        paths = [r.path for r in app.routes]
        assert "/api/v1/benchmark/dashboard" in paths
        assert "/api/v1/benchmark/suites" in paths
        assert "/api/v1/benchmark/runs" in paths
        assert "/api/v1/benchmark/suites/{suite_id}" in paths
        assert "/api/v1/benchmark/runs/{run_id}" in paths
        assert "/api/v1/benchmark/runs/{run_id}/complete" in paths
