"""Health 端点测试 — 基础健康检查 / 深度探测 / 系统信息。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthSimple:
    """GET /health 基础健康检查。"""

    def test_health_ok(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "kasaya-backend"


class TestHealthDeep:
    """GET /health/deep 深度探测（DB + Redis）。"""

    @patch("app.api.health._gather_probes", new_callable=AsyncMock)
    def test_deep_all_healthy(self, mock_gather: AsyncMock) -> None:
        # _gather_probes 返回 tuple(db_result, redis_result)
        mock_gather.return_value = (
            {"status": "ok", "latency_ms": 5.0, "version": "PostgreSQL 16"},
            {"status": "ok", "version": "7.0.0", "latency_ms": 2.0},
        )
        resp = client.get("/health/deep")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["components"]["database"]["status"] == "ok"
        assert body["components"]["redis"]["status"] == "ok"

    @patch("app.api.health._gather_probes", new_callable=AsyncMock)
    def test_deep_db_down(self, mock_gather: AsyncMock) -> None:
        mock_gather.return_value = (
            {"status": "error", "error": "connection refused"},
            {"status": "ok", "version": "7.0.0", "latency_ms": 2.0},
        )
        resp = client.get("/health/deep")
        body = resp.json()
        assert body["status"] in ("degraded", "error")
        assert body["components"]["database"]["status"] == "error"

    @patch("app.api.health._gather_probes", new_callable=AsyncMock)
    def test_deep_redis_down(self, mock_gather: AsyncMock) -> None:
        mock_gather.return_value = (
            {"status": "ok", "latency_ms": 5.0},
            {"status": "error", "error": "connection refused"},
        )
        resp = client.get("/health/deep")
        body = resp.json()
        assert body["status"] in ("degraded", "error")
        assert body["components"]["redis"]["status"] == "error"

    @patch("app.api.health._gather_probes", new_callable=AsyncMock)
    def test_deep_all_down(self, mock_gather: AsyncMock) -> None:
        mock_gather.return_value = (
            {"status": "error", "error": "timeout"},
            {"status": "error", "error": "timeout"},
        )
        resp = client.get("/health/deep")
        body = resp.json()
        assert body["status"] in ("degraded", "error")


class TestSystemInfo:
    """GET /system/info 系统信息端点。"""

    def test_system_info_returns_config(self) -> None:
        resp = client.get("/system/info")
        assert resp.status_code == 200
        body = resp.json()
        # system/info 返回 APM / 监控相关配置
        assert isinstance(body, dict)
