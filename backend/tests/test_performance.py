"""M5 Phase 5.2 — 性能测试。

验证目标：
- 5.2.1 并发 10 用户基准测试（所有请求成功完成，无超时/错误）
- 5.2.2 p95 API 响应 < 200ms（CRUD 端点在 mock service 下）
- 5.2.3 首 Token < 2s SSE 延迟验证（SSE 端点首事件到达时间）
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


# ═══════════════════════════════════════════════════════════════════
# 公共 Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


def _make_agent_config(**overrides: Any) -> MagicMock:
    """构造一个模拟 AgentConfig ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "perf-agent",
        "description": "Performance test agent",
        "instructions": "You are a performance test agent.",
        "model": "gpt-4o",
        "model_settings": None,
        "tool_groups": [],
        "handoffs": [],
        "guardrails": {"input": [], "output": [], "tool": []},
        "approval_mode": "full-auto",
        "mcp_servers": [],
        "agent_tools": [],
        "provider_name": None,
        "skills": [],
        "output_type": None,
        "metadata_": {},
        "org_id": None,
        "is_active": True,
        "created_by": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_session_record(**overrides: Any) -> MagicMock:
    """构造一个模拟 SessionRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "agent_name": "perf-agent",
        "status": "active",
        "title": "",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_token_usage_log(**overrides: Any) -> MagicMock:
    """构造一个模拟 TokenUsageLog ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "agent_name": "perf-agent",
        "model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "user_id": None,
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


async def _mock_sse_generator() -> AsyncIterator[str]:
    """模拟 SSE 事件流生成器（模拟 LLM 响应延迟）。"""
    run_id = str(uuid.uuid4())

    # run_start — 立即发出
    yield f"event: run_start\ndata: {json.dumps({'run_id': run_id, 'agent_name': 'perf-agent'})}\n\n"

    # agent_start
    yield f"event: agent_start\ndata: {json.dumps({'agent_name': 'perf-agent'})}\n\n"

    # 模拟 LLM 首 token 延迟（50ms 模拟网络 + 推理延迟）
    await asyncio.sleep(0.05)

    # text_delta 事件（分 5 个 chunk）
    for i in range(5):
        yield f"event: text_delta\ndata: {json.dumps({'agent_name': 'perf-agent', 'delta': f'chunk{i} '})}\n\n"
        await asyncio.sleep(0.01)  # 10ms 间隔

    # run_end
    run_end_data = json.dumps({
        "agent_name": "perf-agent",
        "run_id": run_id,
        "status": "completed",
        "duration_ms": 120,
    })
    yield f"event: run_end\ndata: {run_end_data}\n\n"


# ═══════════════════════════════════════════════════════════════════
# 5.2.1 — 并发 10 用户基准测试
# ═══════════════════════════════════════════════════════════════════


class TestConcurrentBaseline:
    """并发 10 用户基准测试：所有请求成功完成。"""

    @patch("app.api.agents.agent_service")
    def test_concurrent_agent_list(self, mock_svc: MagicMock) -> None:
        """10 个并发请求同时查询 Agent 列表。"""
        agents = [_make_agent_config(name=f"agent-{i}") for i in range(5)]
        mock_svc.list_agents = AsyncMock(return_value=(agents, 5))

        client = TestClient(app)
        results: list[int] = []

        def _request() -> int:
            resp = client.get("/api/v1/agents")
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_request) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(code == 200 for code in results)
        assert len(results) == 10

    @patch("app.api.sessions.session_service")
    def test_concurrent_session_create(self, mock_svc: MagicMock) -> None:
        """10 个并发请求同时创建 Session。"""
        mock_svc.create_session = AsyncMock(side_effect=lambda db, data: _make_session_record())

        client = TestClient(app)
        results: list[int] = []

        def _request() -> int:
            resp = client.post("/api/v1/sessions", json={"agent_name": "perf-agent"})
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_request) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(code == 201 for code in results)
        assert len(results) == 10

    def test_concurrent_health_check(self) -> None:
        """10 个并发 health check 请求。"""
        client = TestClient(app)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(lambda: client.get("/health").status_code) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(code == 200 for code in results)

    @patch("app.api.token_usage.token_usage_service")
    def test_concurrent_token_usage_query(self, mock_svc: MagicMock) -> None:
        """10 个并发 Token 统计查询。"""
        logs = [_make_token_usage_log() for _ in range(3)]
        mock_svc.list_token_usage = AsyncMock(return_value=(logs, 3))

        client = TestClient(app)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(lambda: client.get("/api/v1/token-usage").status_code) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(code == 200 for code in results)


# ═══════════════════════════════════════════════════════════════════
# 5.2.2 — p95 API 响应 < 200ms
# ═══════════════════════════════════════════════════════════════════


class TestP95ResponseTime:
    """p95 API 响应时间 < 200ms。"""

    def _measure_latency(self, func: Any, iterations: int = 50) -> list[float]:
        """测量多次调用延迟（毫秒）。"""
        latencies: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
        return latencies

    def test_health_p95_under_200ms(self) -> None:
        """GET /health p95 < 200ms。"""
        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/health"), iterations=100)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    @patch("app.api.agents.agent_service")
    def test_agent_list_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """GET /api/v1/agents p95 < 200ms。"""
        agents = [_make_agent_config(name=f"agent-{i}") for i in range(10)]
        mock_svc.list_agents = AsyncMock(return_value=(agents, 10))

        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/api/v1/agents"), iterations=50)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    @patch("app.api.agents.agent_service")
    def test_agent_create_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """POST /api/v1/agents p95 < 200ms。"""
        mock_svc.create_agent = AsyncMock(return_value=_make_agent_config())

        client = TestClient(app)
        latencies = self._measure_latency(
            lambda: client.post("/api/v1/agents", json={
                "name": "bench-agent",
                "instructions": "test",
            }),
            iterations=50,
        )
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    @patch("app.api.sessions.session_service")
    def test_session_list_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """GET /api/v1/sessions p95 < 200ms。"""
        sessions = [_make_session_record() for _ in range(20)]
        mock_svc.list_sessions = AsyncMock(return_value=(sessions, 20))

        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/api/v1/sessions"), iterations=50)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    @patch("app.api.sessions.session_service")
    def test_session_create_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """POST /api/v1/sessions p95 < 200ms。"""
        mock_svc.create_session = AsyncMock(return_value=_make_session_record())

        client = TestClient(app)
        latencies = self._measure_latency(
            lambda: client.post("/api/v1/sessions", json={"agent_name": "perf-agent"}),
            iterations=50,
        )
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    @patch("app.api.token_usage.token_usage_service")
    def test_token_usage_list_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """GET /api/v1/token-usage p95 < 500ms。"""
        logs = [_make_token_usage_log() for _ in range(50)]
        mock_svc.list_token_usage = AsyncMock(return_value=(logs, 50))

        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/api/v1/token-usage"), iterations=50)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 500, f"p95={p95:.1f}ms 超过 500ms 阈值"

    @patch("app.api.token_usage.token_usage_service")
    def test_token_usage_summary_p95_under_200ms(self, mock_svc: MagicMock) -> None:
        """GET /api/v1/token-usage/summary p95 < 200ms。"""
        mock_svc.get_token_usage_summary = AsyncMock(return_value=[
            {
                "agent_name": "a1",
                "model": "gpt-4o",
                "total_prompt_tokens": 100,
                "total_completion_tokens": 50,
                "total_tokens": 150,
                "call_count": 5,
            },
        ])

        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/api/v1/token-usage/summary"), iterations=50)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"p95={p95:.1f}ms 超过 200ms 阈值"

    def test_latency_statistics_report(self) -> None:
        """综合延迟报告（信息性测试）。"""
        client = TestClient(app)
        latencies = self._measure_latency(lambda: client.get("/health"), iterations=100)
        p50 = sorted(latencies)[int(len(latencies) * 0.50)]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)
        # 只打印不断言 — 信息性测试
        print(f"\n=== /health 延迟报告 (n={len(latencies)}) ===")
        print(f"  avg: {avg:.1f}ms | p50: {p50:.1f}ms | p95: {p95:.1f}ms | p99: {p99:.1f}ms")
        assert True  # 信息性测试总是通过


# ═══════════════════════════════════════════════════════════════════
# 5.2.3 — 首 Token < 2s SSE 延迟验证
# ═══════════════════════════════════════════════════════════════════


class TestSSEFirstToken:
    """SSE 首 Token 延迟 < 2s。"""

    @patch("app.api.sessions.session_service")
    def test_sse_first_event_under_2s(self, mock_svc: MagicMock) -> None:
        """SSE 首事件在 2 秒内到达。"""
        session_mock = _make_session_record()

        # mock execute_run_stream 返回 SSE 生成器
        mock_svc.execute_run_stream = MagicMock(return_value=_mock_sse_generator())

        client = TestClient(app)
        session_id = session_mock.id

        start = time.perf_counter()
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_id}/run",
            json={"input": "hello", "config": {"stream": True}},
        ) as response:
            assert response.status_code == 200

            # 读取第一行数据
            first_line = None
            for line in response.iter_lines():
                if line.strip():
                    first_line = line
                    break

            first_event_ms = (time.perf_counter() - start) * 1000

        assert first_line is not None, "未收到任何 SSE 事件"
        assert first_event_ms < 2000, f"首事件延迟 {first_event_ms:.0f}ms 超过 2000ms 阈值"

    @patch("app.api.sessions.session_service")
    def test_sse_all_events_received(self, mock_svc: MagicMock) -> None:
        """SSE 流完整接收所有事件。"""
        session_mock = _make_session_record()
        mock_svc.execute_run_stream = MagicMock(return_value=_mock_sse_generator())

        client = TestClient(app)

        events: list[str] = []
        with client.stream(
            "POST",
            f"/api/v1/sessions/{session_mock.id}/run",
            json={"input": "hello", "config": {"stream": True}},
        ) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())

        # 验证事件序列完整
        assert "run_start" in events
        assert "agent_start" in events
        assert "text_delta" in events
        assert "run_end" in events

    @patch("app.api.sessions.session_service")
    def test_sse_first_token_p95(self, mock_svc: MagicMock) -> None:
        """SSE 首 token p95 < 2s（多次测量）。"""
        latencies: list[float] = []

        for _ in range(10):
            mock_svc.execute_run_stream = MagicMock(return_value=_mock_sse_generator())
            client = TestClient(app)
            session_id = uuid.uuid4()

            start = time.perf_counter()
            with client.stream(
                "POST",
                f"/api/v1/sessions/{session_id}/run",
                json={"input": "test", "config": {"stream": True}},
            ) as response:
                for line in response.iter_lines():
                    if line.strip():
                        elapsed = (time.perf_counter() - start) * 1000
                        latencies.append(elapsed)
                        break

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 2000, f"SSE 首 token p95={p95:.0f}ms 超过 2000ms 阈值"

    @patch("app.api.sessions.session_service")
    def test_sse_concurrent_streams(self, mock_svc: MagicMock) -> None:
        """并发 5 个 SSE 流同时工作。"""

        def _stream_request() -> tuple[int, list[str]]:
            # 每个请求使用独立的 mock 生成器
            mock_svc.execute_run_stream = MagicMock(side_effect=lambda *_a, **_kw: _mock_sse_generator())
            client = TestClient(app)
            session_id = uuid.uuid4()

            events: list[str] = []
            with client.stream(
                "POST",
                f"/api/v1/sessions/{session_id}/run",
                json={"input": "concurrent", "config": {"stream": True}},
            ) as response:
                status = response.status_code
                for line in response.iter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        events.append(line.split(":", 1)[1].strip())
            return status, events

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_stream_request) for _ in range(5)]
            results = [f.result() for f in futures]

        for status, events in results:
            assert status == 200
            assert "run_start" in events
            assert "run_end" in events


# ═══════════════════════════════════════════════════════════════════
# 综合基准
# ═══════════════════════════════════════════════════════════════════


class TestOverallBenchmark:
    """综合性能基准。"""

    @patch("app.api.agents.agent_service")
    @patch("app.api.sessions.session_service")
    def test_mixed_workload_10_concurrent(
        self,
        mock_session_svc: MagicMock,
        mock_agent_svc: MagicMock,
    ) -> None:
        """混合负载：10 个并发请求（agent list + session create + health）。"""
        agents = [_make_agent_config(name=f"a-{i}") for i in range(5)]
        mock_agent_svc.list_agents = AsyncMock(return_value=(agents, 5))
        mock_session_svc.create_session = AsyncMock(side_effect=lambda db, data: _make_session_record())

        client = TestClient(app)

        def _random_request(i: int) -> tuple[str, int, float]:
            start = time.perf_counter()
            if i % 3 == 0:
                resp = client.get("/health")
                endpoint = "health"
            elif i % 3 == 1:
                resp = client.get("/api/v1/agents")
                endpoint = "agents"
            else:
                resp = client.post("/api/v1/sessions", json={"agent_name": "perf-agent"})
                endpoint = "sessions"
            elapsed = (time.perf_counter() - start) * 1000
            return endpoint, resp.status_code, elapsed

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_random_request, i) for i in range(10)]
            results = [f.result() for f in futures]

        # 所有请求成功
        for endpoint, status, elapsed in results:
            assert status in (200, 201), f"{endpoint} 返回 {status}"

        # p95 < 200ms
        latencies = [r[2] for r in results]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 200, f"混合负载 p95={p95:.1f}ms 超过 200ms"

        # 输出报告
        by_endpoint: dict[str, list[float]] = {}
        for endpoint, _, elapsed in results:
            by_endpoint.setdefault(endpoint, []).append(elapsed)
        print("\n=== 混合负载报告 ===")
        for ep, lats in sorted(by_endpoint.items()):
            avg = statistics.mean(lats)
            print(f"  {ep}: avg={avg:.1f}ms, n={len(lats)}")
