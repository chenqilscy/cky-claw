"""S4 Event Sourcing — 后端 EventRecord / EventJournal / Events API 测试。

使用 mock 方式测试，不依赖 PostgreSQL。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_record(**overrides) -> MagicMock:
    """构造一个模拟 EventRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults: dict = {
        "id": uuid.uuid4(),
        "sequence": 1,
        "event_type": "run_start",
        "run_id": "run-001",
        "session_id": None,
        "agent_name": "bot",
        "span_id": None,
        "timestamp": now,
        "payload": {},
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestEventSchemas:
    """事件 API Schema 校验。"""

    def test_event_response_basic(self) -> None:
        """EventResponse 正常属性。"""
        from app.api.events import EventResponse

        now = datetime.now(timezone.utc)
        resp = EventResponse(
            event_id="evt-1",
            sequence=1,
            event_type="run_start",
            run_id="run-001",
            timestamp=now,
        )
        assert resp.event_id == "evt-1"
        assert resp.event_type == "run_start"
        assert resp.session_id is None

    def test_event_response_with_all_fields(self) -> None:
        """EventResponse 全字段。"""
        from app.api.events import EventResponse

        now = datetime.now(timezone.utc)
        sid = str(uuid.uuid4())
        resp = EventResponse(
            event_id="evt-2",
            sequence=5,
            event_type="tool_call_end",
            run_id="run-002",
            session_id=sid,
            agent_name="assistant",
            span_id="span-abc",
            timestamp=now,
            payload={"tool_name": "search"},
        )
        assert resp.agent_name == "assistant"
        assert resp.payload == {"tool_name": "search"}

    def test_event_list_response(self) -> None:
        """EventListResponse 结构。"""
        from app.api.events import EventListResponse

        resp = EventListResponse(items=[], total=0)
        assert resp.items == []
        assert resp.total == 0

    def test_event_stats_response(self) -> None:
        """EventStatsResponse 结构。"""
        from app.api.events import EventStatsResponse

        resp = EventStatsResponse(
            total_events=42,
            event_type_counts={"run_start": 10, "llm_call_end": 32},
            run_count=5,
        )
        assert resp.total_events == 42
        assert resp.run_count == 5

    def test_run_config_event_journal_enabled(self) -> None:
        """RunConfig Schema 包含 event_journal_enabled 字段。"""
        from app.schemas.session import RunConfig

        cfg = RunConfig()
        assert cfg.event_journal_enabled is False

        cfg2 = RunConfig(event_journal_enabled=True)
        assert cfg2.event_journal_enabled is True


# ---------------------------------------------------------------------------
# Service 测试 — SQLAlchemyEventJournal
# ---------------------------------------------------------------------------


class TestSQLAlchemyEventJournal:
    """SQLAlchemyEventJournal 单元测试。"""

    @pytest.mark.anyio()
    async def test_append_creates_record(self) -> None:
        """append 写入 EventRecord 并 flush。"""
        from ckyclaw_framework.events.journal import EventEntry
        from ckyclaw_framework.events.types import EventType

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from app.services.event_journal import SQLAlchemyEventJournal

        journal = SQLAlchemyEventJournal(mock_db)

        entry = EventEntry(
            event_type=EventType.RUN_START,
            run_id="run-100",
            agent_name="bot",
        )
        await journal.append(entry)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        assert entry.sequence == 1

    @pytest.mark.anyio()
    async def test_append_assigns_sequence(self) -> None:
        """多次 append 序列号递增。"""
        from ckyclaw_framework.events.journal import EventEntry
        from ckyclaw_framework.events.types import EventType

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from app.services.event_journal import SQLAlchemyEventJournal

        journal = SQLAlchemyEventJournal(mock_db)

        entries = [
            EventEntry(event_type=EventType.RUN_START, run_id="r1"),
            EventEntry(event_type=EventType.AGENT_START, run_id="r1"),
            EventEntry(event_type=EventType.LLM_CALL_START, run_id="r1"),
        ]
        for e in entries:
            await journal.append(e)

        assert entries[0].sequence == 1
        assert entries[1].sequence == 2
        assert entries[2].sequence == 3

    @pytest.mark.anyio()
    async def test_query_with_filters(self) -> None:
        """_query 构建正确的 SQLAlchemy 条件。"""
        from ckyclaw_framework.events.journal import EventEntry
        from ckyclaw_framework.events.types import EventType

        # 构造 mock 数据库返回
        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.sequence = 1
        mock_record.event_type = "run_start"
        mock_record.run_id = "run-200"
        mock_record.session_id = None
        mock_record.agent_name = "bot"
        mock_record.span_id = None
        mock_record.timestamp = datetime.now(timezone.utc)
        mock_record.payload = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_record]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.event_journal import SQLAlchemyEventJournal

        journal = SQLAlchemyEventJournal(mock_db)
        events = await journal.get_events(
            run_id="run-200",
            event_types=[EventType.RUN_START],
            limit=10,
        )

        assert len(events) == 1
        assert events[0].run_id == "run-200"
        assert events[0].event_type == EventType.RUN_START
        mock_db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Service 测试 — _save_events_from_journal
# ---------------------------------------------------------------------------


class TestSaveEventsFromJournal:
    """_save_events_from_journal 辅助函数测试。"""

    @pytest.mark.anyio()
    async def test_empty_journal_noop(self) -> None:
        """空 journal 不写入。"""
        from ckyclaw_framework.events.journal import InMemoryEventJournal

        from app.services.session import _save_events_from_journal

        mock_db = AsyncMock()
        mock_db.add_all = MagicMock()
        mock_db.flush = AsyncMock()

        journal = InMemoryEventJournal()
        await _save_events_from_journal(mock_db, journal)

        mock_db.add_all.assert_not_called()
        mock_db.flush.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_saves_events(self) -> None:
        """有事件时通过 savepoint 写入 EventRecord 列表。"""
        from ckyclaw_framework.events.journal import EventEntry, InMemoryEventJournal
        from ckyclaw_framework.events.types import EventType

        from app.services.session import _save_events_from_journal

        mock_db = AsyncMock()
        mock_db.add_all = MagicMock()
        # begin_nested 返回一个异步上下文管理器
        mock_nested = AsyncMock()
        mock_nested.__aenter__ = AsyncMock()
        mock_nested.__aexit__ = AsyncMock(return_value=False)
        mock_db.begin_nested = MagicMock(return_value=mock_nested)

        journal = InMemoryEventJournal()
        await journal.append(EventEntry(
            event_type=EventType.RUN_START, run_id="run-300",
        ))
        await journal.append(EventEntry(
            event_type=EventType.AGENT_START, run_id="run-300",
            agent_name="bot",
        ))

        await _save_events_from_journal(mock_db, journal)

        mock_db.add_all.assert_called_once()
        records = mock_db.add_all.call_args[0][0]
        assert len(records) == 2
        mock_db.begin_nested.assert_called_once()

    @pytest.mark.anyio()
    async def test_handles_exception(self) -> None:
        """异常时不影响外部事务。"""
        from ckyclaw_framework.events.journal import EventEntry, InMemoryEventJournal
        from ckyclaw_framework.events.types import EventType

        from app.services.session import _save_events_from_journal

        # 模拟 begin_nested 抛出异常
        mock_db = AsyncMock()
        mock_db.begin_nested = MagicMock(side_effect=Exception("Savepoint error"))

        journal = InMemoryEventJournal()
        await journal.append(EventEntry(
            event_type=EventType.RUN_START, run_id="run-err",
        ))

        # 不应抛出异常
        await _save_events_from_journal(mock_db, journal)


# ---------------------------------------------------------------------------
# API 路由测试
# ---------------------------------------------------------------------------


class TestEventsReplayAPI:
    """GET /api/v1/events/replay/{run_id} 测试。"""

    def test_replay_empty(self, client: TestClient) -> None:
        """无事件返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        with patch("app.api.events.get_db", return_value=mock_db):
            app.dependency_overrides[__import__("app.core.deps", fromlist=["get_db"]).get_db] = lambda: mock_db
            try:
                resp = client.get("/api/v1/events/replay/run-001")
                assert resp.status_code == 200
                body = resp.json()
                assert body["items"] == []
                assert body["total"] == 0
            finally:
                app.dependency_overrides.clear()

    def test_replay_with_events(self, client: TestClient) -> None:
        """有事件正常返回。"""
        now = datetime.now(timezone.utc)
        ev = _make_event_record(
            sequence=1,
            event_type="run_start",
            run_id="run-replay",
            timestamp=now,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ev]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get("/api/v1/events/replay/run-replay")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["items"]) == 1
            assert body["items"][0]["run_id"] == "run-replay"
            assert body["total"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_replay_with_filter(self, client: TestClient) -> None:
        """带 event_type 过滤。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get(
                "/api/v1/events/replay/run-001",
                params={"event_type": "llm_call_start", "limit": 50},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_replay_after_sequence(self, client: TestClient) -> None:
        """带 after_sequence 增量查询。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get(
                "/api/v1/events/replay/run-001",
                params={"after_sequence": 5},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestSessionEventsAPI:
    """GET /api/v1/events/sessions/{session_id} 测试。"""

    def test_session_events_empty(self, client: TestClient) -> None:
        """空会话事件。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        from app.core.deps import get_db

        sid = uuid.uuid4()
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/events/sessions/{sid}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["items"] == []
        finally:
            app.dependency_overrides.clear()

    def test_session_events_with_data(self, client: TestClient) -> None:
        """有事件正常返回。"""
        now = datetime.now(timezone.utc)
        sid = uuid.uuid4()
        ev = _make_event_record(
            sequence=1,
            event_type="agent_start",
            run_id="run-sess",
            session_id=sid,
            timestamp=now,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ev]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get(f"/api/v1/events/sessions/{sid}")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["items"]) == 1
            assert body["items"][0]["event_type"] == "agent_start"
        finally:
            app.dependency_overrides.clear()


class TestEventStatsAPI:
    """GET /api/v1/events/stats 测试。"""

    def test_stats_empty(self, client: TestClient) -> None:
        """无数据返回零值。"""
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 0

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = []

        mock_run_result = MagicMock()
        mock_run_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_type_result, mock_run_result]
        )

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get("/api/v1/events/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_events"] == 0
            assert body["event_type_counts"] == {}
            assert body["run_count"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_stats_with_data(self, client: TestClient) -> None:
        """有数据返回统计。"""
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 15

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("run_start", 3),
            ("llm_call_end", 7),
            ("tool_call_start", 5),
        ]

        mock_run_result = MagicMock()
        mock_run_result.scalar.return_value = 3

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_type_result, mock_run_result]
        )

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get("/api/v1/events/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_events"] == 15
            assert body["event_type_counts"]["llm_call_end"] == 7
            assert body["run_count"] == 3
        finally:
            app.dependency_overrides.clear()

    def test_stats_with_run_id_filter(self, client: TestClient) -> None:
        """按 run_id 过滤统计。"""
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 5

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [("run_start", 1), ("run_end", 1)]

        mock_run_result = MagicMock()
        mock_run_result.scalar.return_value = 1

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_type_result, mock_run_result]
        )

        from app.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get("/api/v1/events/stats", params={"run_id": "run-filter"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_events"] == 5
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# EventRecord 模型测试
# ---------------------------------------------------------------------------


class TestEventRecordModel:
    """EventRecord ORM 模型基本属性测试。"""

    def test_tablename(self) -> None:
        """表名正确。"""
        from app.models.event import EventRecord

        assert EventRecord.__tablename__ == "events"

    def test_columns_exist(self) -> None:
        """关键列存在。"""
        from app.models.event import EventRecord

        cols = {c.name for c in EventRecord.__table__.columns}
        expected = {
            "id", "sequence", "event_type", "run_id", "session_id",
            "agent_name", "span_id", "timestamp", "payload", "created_at",
        }
        assert expected.issubset(cols)

    def test_indexes(self) -> None:
        """关键索引列。"""
        from app.models.event import EventRecord

        indexed_cols = {
            c.name for c in EventRecord.__table__.columns if c.index
        }
        assert "sequence" in indexed_cols
        assert "event_type" in indexed_cols
        assert "run_id" in indexed_cols
        assert "timestamp" in indexed_cols
