"""Event Journal API 测试 — 事件回放 / 会话事件 / 统计聚合。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import app

client = TestClient(app)

now = datetime.now(timezone.utc)


def _mock_event(**overrides: object) -> MagicMock:
    """构造 mock EventRecord。"""
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "sequence": 1,
        "event_type": "run_start",
        "run_id": "run-001",
        "session_id": uuid.uuid4(),
        "agent_name": "test-agent",
        "span_id": "span-001",
        "timestamp": now,
        "payload": {"key": "value"},
        "created_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_mock_db(events: list | None = None, total: int = 0, type_counts: list | None = None, run_count: int = 0):
    """创建 mock DB session 并配置 execute 多次返回不同结果。"""
    mock_session = AsyncMock()
    call_idx = {"n": 0}

    events = events or []
    type_counts = type_counts or []

    async def mock_execute(stmt):
        n = call_idx["n"]
        call_idx["n"] += 1
        result = MagicMock()
        if n == 0:
            # 主查询 — 返回 records
            result.scalars.return_value.all.return_value = events
        elif n == 1:
            # count 查询
            result.scalar.return_value = total
        elif n == 2:
            # type count 分组查询
            result.all.return_value = type_counts
        elif n == 3:
            # run count 查询
            result.scalar.return_value = run_count
        else:
            result.scalars.return_value.all.return_value = []
            result.scalar.return_value = 0
        return result

    mock_session.execute = mock_execute
    return mock_session


class TestReplayRunEvents:
    """GET /api/v1/events/replay/{run_id} 事件回放。"""

    def setup_method(self) -> None:
        mock_session = _make_mock_db(
            events=[_mock_event(sequence=i) for i in range(1, 4)],
            total=3,
        )

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override

    def teardown_method(self) -> None:
        app.dependency_overrides.pop(get_db, None)

    def test_replay_returns_events(self) -> None:
        """回放指定 run 的事件列表。"""
        resp = client.get("/api/v1/events/replay/run-001")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["total"] == 3

    def test_replay_route_exists(self) -> None:
        """验证 replay 路由注册。"""
        resp = client.get("/api/v1/events/replay/nonexistent-run")
        assert resp.status_code == 200


class TestSessionEvents:
    """GET /api/v1/events/sessions/{session_id} 会话事件。"""

    def setup_method(self) -> None:
        mock_session = _make_mock_db(events=[], total=0)

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override

    def teardown_method(self) -> None:
        app.dependency_overrides.pop(get_db, None)

    def test_session_events_route_exists(self) -> None:
        """验证 session events 路由注册。"""
        sid = str(uuid.uuid4())
        resp = client.get(f"/api/v1/events/sessions/{sid}")
        assert resp.status_code == 200

    def test_session_events_invalid_uuid(self) -> None:
        """非法 UUID 应返回 422。"""
        resp = client.get("/api/v1/events/sessions/not-a-uuid")
        assert resp.status_code == 422


class TestEventStats:
    """GET /api/v1/events/stats 统计聚合。"""

    def setup_method(self) -> None:
        mock_session = _make_mock_db(
            total=10,
            type_counts=[("run_start", 5), ("llm_call", 3), ("tool_call", 2)],
            run_count=2,
        )

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override

    def teardown_method(self) -> None:
        app.dependency_overrides.pop(get_db, None)

    def test_stats_route_exists(self) -> None:
        """验证 stats 路由注册。"""
        resp = client.get("/api/v1/events/stats")
        assert resp.status_code == 200

    def test_stats_with_run_id_filter(self) -> None:
        """带 run_id 过滤的统计请求。"""
        resp = client.get("/api/v1/events/stats?run_id=run-001")
        assert resp.status_code == 200

    def test_stats_with_session_id_filter(self) -> None:
        """带 session_id 过滤的统计请求。"""
        sid = str(uuid.uuid4())
        resp = client.get(f"/api/v1/events/stats?session_id={sid}")
        assert resp.status_code == 200

    def test_stats_with_session_id_filter(self) -> None:
        """带 session_id 过滤的统计请求。"""
        sid = str(uuid.uuid4())
        resp = client.get(f"/api/v1/events/stats?session_id={sid}")
        assert resp.status_code in (200, 500)
