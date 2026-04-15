"""Checkpoint PostgresBackend + API 测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.checkpoint import CheckpointRecord
from app.schemas.checkpoint import CheckpointListResponse, CheckpointResponse
from app.services.checkpoint_backend import PostgresCheckpointBackend
from ckyclaw_framework.checkpoint import Checkpoint, CheckpointBackend
from ckyclaw_framework.model.message import Message, MessageRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _make_checkpoint_record(**overrides: object) -> MagicMock:
    """构造 CheckpointRecord ORM mock。"""
    defaults: dict[str, Any] = {
        "checkpoint_id": uuid.uuid4().hex,
        "run_id": "run-001",
        "turn_count": 1,
        "current_agent_name": "test-agent",
        "messages": [{"role": "user", "content": "hello", "timestamp": _NOW.isoformat()}],
        "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "context": {"key": "val"},
        "created_at": _NOW,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# PostgresCheckpointBackend 单元测试
# ---------------------------------------------------------------------------


class TestPostgresCheckpointBackend:
    """PostgresCheckpointBackend 核心方法测试。"""

    @pytest.mark.asyncio
    async def test_save(self) -> None:
        """save 方法应创建 ORM 记录并 flush。"""
        db = AsyncMock()
        backend = PostgresCheckpointBackend(db)

        msg = Message(role=MessageRole.USER, content="hello")
        cp = Checkpoint(
            checkpoint_id="cp-001",
            run_id="run-001",
            turn_count=1,
            current_agent_name="agent-a",
            messages=[msg],
            token_usage={"total_tokens": 10},
            context={"k": "v"},
        )
        await backend.save(cp)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()

        record = db.add.call_args[0][0]
        assert isinstance(record, CheckpointRecord)
        assert record.checkpoint_id == "cp-001"
        assert record.run_id == "run-001"
        assert len(record.messages) == 1
        assert record.messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_save_with_dict_messages(self) -> None:
        """messages 中混有 dict 时也能正确序列化。"""
        db = AsyncMock()
        backend = PostgresCheckpointBackend(db)

        cp = Checkpoint(
            checkpoint_id="cp-002",
            run_id="run-001",
            messages=[{"role": "user", "content": "raw dict"}],  # type: ignore[list-item]
        )
        await backend.save(cp)
        record = db.add.call_args[0][0]
        assert record.messages[0]["content"] == "raw dict"

    @pytest.mark.asyncio
    async def test_load_latest_found(self) -> None:
        """load_latest 找到记录时返回 Checkpoint。"""
        db = AsyncMock()
        mock_result = MagicMock()
        row = _make_checkpoint_record(run_id="run-001", turn_count=3)
        mock_result.scalar_one_or_none.return_value = row
        db.execute = AsyncMock(return_value=mock_result)

        backend = PostgresCheckpointBackend(db)
        cp = await backend.load_latest("run-001")

        assert cp is not None
        assert cp.run_id == "run-001"
        assert cp.turn_count == 3

    @pytest.mark.asyncio
    async def test_load_latest_not_found(self) -> None:
        """load_latest 无记录时返回 None。"""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        backend = PostgresCheckpointBackend(db)
        cp = await backend.load_latest("run-nonexist")
        assert cp is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self) -> None:
        """list_checkpoints 返回按 turn_count 排列的列表。"""
        db = AsyncMock()
        mock_result = MagicMock()
        r1 = _make_checkpoint_record(turn_count=1)
        r2 = _make_checkpoint_record(turn_count=2)
        mock_result.scalars.return_value.all.return_value = [r1, r2]
        db.execute = AsyncMock(return_value=mock_result)

        backend = PostgresCheckpointBackend(db)
        cps = await backend.list_checkpoints("run-001")

        assert len(cps) == 2
        assert cps[0].turn_count == 1
        assert cps[1].turn_count == 2

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """delete 调用 SQL DELETE 并 flush。"""
        db = AsyncMock()
        backend = PostgresCheckpointBackend(db)
        await backend.delete("run-001")

        db.execute.assert_awaited_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_to_checkpoint_deserializes_messages(self) -> None:
        """_to_checkpoint 应将 JSONB messages 反序列化为 Message 对象。"""
        record = _make_checkpoint_record(
            messages=[
                {"role": "user", "content": "hello", "timestamp": _NOW.isoformat()},
                {"role": "assistant", "content": "hi", "timestamp": _NOW.isoformat()},
            ]
        )
        cp = PostgresCheckpointBackend._to_checkpoint(record)
        assert len(cp.messages) == 2
        assert isinstance(cp.messages[0], Message)
        assert cp.messages[0].role == MessageRole.USER
        assert cp.messages[1].content == "hi"

    def test_implements_abc(self) -> None:
        """PostgresCheckpointBackend 实现了 CheckpointBackend ABC。"""
        assert issubclass(PostgresCheckpointBackend, CheckpointBackend)


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestCheckpointSchema:
    """Checkpoint Schema 验证。"""

    def test_checkpoint_response(self) -> None:
        resp = CheckpointResponse(
            checkpoint_id="cp-001",
            run_id="run-001",
            turn_count=1,
            current_agent_name="agent-a",
            messages=[{"role": "user", "content": "hello"}],
            token_usage={"total_tokens": 10},
            context={},
            created_at=_NOW,
        )
        assert resp.checkpoint_id == "cp-001"

    def test_checkpoint_list_response(self) -> None:
        resp = CheckpointListResponse(data=[], total=0)
        assert resp.total == 0


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


def _mock_db_with_records(*records: MagicMock) -> AsyncMock:
    """构造异步 DB session mock，支持 execute 返回 records。"""
    session = AsyncMock()
    result = MagicMock()
    # 用于 count 和 list 两种查询
    result.scalar_one.return_value = len(records)
    result.scalars.return_value.all.return_value = list(records)
    result.scalar_one_or_none.return_value = records[0] if records else None
    session.execute = AsyncMock(return_value=result)
    return session


class TestCheckpointListAPI:
    """GET /api/v1/checkpoints 端点测试。"""

    def test_list_checkpoints(self, client: TestClient) -> None:
        r1 = _make_checkpoint_record(turn_count=1)
        r2 = _make_checkpoint_record(turn_count=2)
        session = _mock_db_with_records(r1, r2)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.get("/api/v1/checkpoints?run_id=run-001")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2

    def test_list_checkpoints_empty(self, client: TestClient) -> None:
        session = _mock_db_with_records()
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.get("/api/v1/checkpoints?run_id=run-empty")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    def test_list_checkpoints_missing_run_id(self, client: TestClient) -> None:
        """缺少 run_id 参数应返回 422。"""
        resp = client.get("/api/v1/checkpoints")
        assert resp.status_code == 422


class TestCheckpointLatestAPI:
    """GET /api/v1/checkpoints/latest 端点测试。"""

    def test_get_latest(self, client: TestClient) -> None:
        r = _make_checkpoint_record(turn_count=5)
        session = _mock_db_with_records(r)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.get("/api/v1/checkpoints/latest?run_id=run-001")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["turn_count"] == 5

    def test_get_latest_not_found(self, client: TestClient) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.get("/api/v1/checkpoints/latest?run_id=run-xxx")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json() is None


class TestCheckpointDeleteAPI:
    """DELETE /api/v1/checkpoints/{run_id} 端点测试。"""

    def test_delete_checkpoints(self, client: TestClient) -> None:
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.delete("/api/v1/checkpoints/run-001")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 204


class TestCheckpointRouteRegistration:
    """验证路由已注册。"""

    def test_routes_registered(self) -> None:
        paths = [route.path for route in app.routes]
        assert "/api/v1/checkpoints" in paths
        assert "/api/v1/checkpoints/latest" in paths
        assert "/api/v1/checkpoints/{run_id}" in paths


class TestCheckpointRecordModel:
    """CheckpointRecord ORM 模型字段测试。"""

    def test_table_name(self) -> None:
        assert CheckpointRecord.__tablename__ == "checkpoints"

    def test_has_required_columns(self) -> None:
        columns = {c.name for c in CheckpointRecord.__table__.columns}
        assert "checkpoint_id" in columns
        assert "run_id" in columns
        assert "turn_count" in columns
        assert "messages" in columns
        assert "token_usage" in columns
        assert "context" in columns
        assert "created_at" in columns
