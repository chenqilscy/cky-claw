"""S6 取消与检查点 — Backend 测试。

覆盖：
- RunRegistry 基础功能
- Cancel Run API
- Resume from Checkpoint API
- Session service cancel_run
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ===========================================================================
# RunRegistry 单元测试
# ===========================================================================


class TestRunRegistry:
    """RunRegistry 内存注册表。"""

    def test_register_and_cancel(self) -> None:
        """注册 run 后可取消。"""
        from app.services.run_registry import RunRegistry
        from kasaya.runner.cancellation import CancellationToken

        registry = RunRegistry()
        token = CancellationToken()
        run_id = "run-001"

        registry.register(run_id, token)
        assert registry.is_running(run_id)

        result = registry.cancel(run_id)
        assert result is True
        assert token.is_cancelled

    def test_cancel_unknown_run(self) -> None:
        """取消不存在的 run 返回 False。"""
        from app.services.run_registry import RunRegistry

        registry = RunRegistry()
        result = registry.cancel("nonexistent")
        assert result is False

    def test_unregister(self) -> None:
        """注销 run 后不可取消。"""
        from app.services.run_registry import RunRegistry
        from kasaya.runner.cancellation import CancellationToken

        registry = RunRegistry()
        token = CancellationToken()
        registry.register("run-002", token)
        registry.unregister("run-002")

        assert not registry.is_running("run-002")
        assert registry.cancel("run-002") is False

    def test_active_count(self) -> None:
        """活跃 run 计数。"""
        from app.services.run_registry import RunRegistry
        from kasaya.runner.cancellation import CancellationToken

        registry = RunRegistry()
        t1 = CancellationToken()
        t2 = CancellationToken()

        registry.register("r1", t1)
        registry.register("r2", t2)
        assert registry.active_count() == 2

        t1.cancel()
        assert registry.active_count() == 1

    def test_is_running_cancelled(self) -> None:
        """已取消的 run 不算 running。"""
        from app.services.run_registry import RunRegistry
        from kasaya.runner.cancellation import CancellationToken

        registry = RunRegistry()
        token = CancellationToken()
        token.cancel()
        registry.register("r3", token)
        assert not registry.is_running("r3")


# ===========================================================================
# Cancel Run API 测试
# ===========================================================================


class TestCancelRunAPI:
    """POST /api/v1/sessions/runs/{run_id}/cancel 端点测试。"""

    @pytest.mark.anyio()
    async def test_cancel_existing_run(self) -> None:
        """取消正在运行的 Run。"""
        from app.services.run_registry import run_registry
        from kasaya.runner.cancellation import CancellationToken

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        token = CancellationToken()
        run_registry.register(run_id, token)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/api/v1/sessions/runs/{run_id}/cancel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["cancelled"] is True
            assert token.is_cancelled
        finally:
            run_registry.unregister(run_id)

    @pytest.mark.anyio()
    async def test_cancel_nonexistent_run(self) -> None:
        """取消不存在的 Run 返回 cancelled=False。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/sessions/runs/nonexistent-run/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is False


# ===========================================================================
# Session service cancel_run 测试
# ===========================================================================


class TestSessionServiceCancelRun:
    """session_service.cancel_run 函数。"""

    def test_cancel_registered_run(self) -> None:
        """取消已注册的 run。"""
        from app.services import session as session_service
        from app.services.run_registry import run_registry
        from kasaya.runner.cancellation import CancellationToken

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        token = CancellationToken()
        run_registry.register(run_id, token)

        try:
            result = session_service.cancel_run(run_id)
            assert result is True
            assert token.is_cancelled
        finally:
            run_registry.unregister(run_id)

    def test_cancel_unregistered_run(self) -> None:
        """取消未注册的 run 返回 False。"""
        from app.services import session as session_service

        result = session_service.cancel_run("nonexistent")
        assert result is False


# ===========================================================================
# Resume from Checkpoint API 测试
# ===========================================================================


class TestResumeFromCheckpointAPI:
    """POST /api/v1/sessions/{session_id}/resume-from-checkpoint 端点测试。"""

    @pytest.mark.anyio()
    async def test_resume_checkpoint_not_found(self) -> None:
        """无 checkpoint 时返回 404。"""
        session_id = str(uuid.uuid4())

        # Mock get_session 和 checkpoint backend
        with (
            patch(
                "app.services.session.get_session",
                new_callable=AsyncMock,
                return_value=MagicMock(agent_name="test-agent"),
            ),
            patch(
                "app.services.checkpoint_backend.PostgresCheckpointBackend.load_latest",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    f"/api/v1/sessions/{session_id}/resume-from-checkpoint",
                    params={"run_id": "run-xyz"},
                    json={"input": "continue"},
                )
            assert resp.status_code == 404
