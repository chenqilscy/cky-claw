"""EventJournal Service 测试 — SQLAlchemy 事件持久化 / 查询过滤 / 序列号。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.event_journal import SQLAlchemyEventJournal


def _make_event_entry(**overrides: object) -> MagicMock:
    """构造 mock EventEntry（ckyclaw_framework 事件对象）。"""
    entry = MagicMock()
    entry.event_id = str(uuid.uuid4())
    entry.sequence = overrides.get("sequence", 0)
    entry.event_type = overrides.get("event_type", MagicMock(value="run_start"))
    entry.run_id = overrides.get("run_id", "run-001")
    entry.session_id = overrides.get("session_id", None)
    entry.agent_name = overrides.get("agent_name", "test-agent")
    entry.span_id = overrides.get("span_id", None)
    entry.timestamp = overrides.get("timestamp", datetime.now(timezone.utc))
    entry.payload = overrides.get("payload", {})
    for k, v in overrides.items():
        setattr(entry, k, v)
    return entry


class TestSQLAlchemyEventJournalInit:
    """初始化与序列号生成。"""

    def test_create_journal(self) -> None:
        db = AsyncMock()
        journal = SQLAlchemyEventJournal(db)
        assert journal is not None

    def test_sequence_starts_at_one(self) -> None:
        db = AsyncMock()
        journal = SQLAlchemyEventJournal(db)
        # _seq_counter 使用 itertools.count(1)，第一个值是 1
        seq = next(journal._seq_counter)
        assert seq == 1

    def test_sequence_increments(self) -> None:
        db = AsyncMock()
        journal = SQLAlchemyEventJournal(db)
        seq1 = next(journal._seq_counter)
        seq2 = next(journal._seq_counter)
        assert seq2 == seq1 + 1


class TestEventJournalAppend:
    """_append 方法 — 事件写入 DB。"""

    @pytest.mark.asyncio
    async def test_append_creates_orm_record(self) -> None:
        """追加事件时创建 ORM 记录并 flush。"""
        db = AsyncMock()
        journal = SQLAlchemyEventJournal(db)

        entry = _make_event_entry()
        with patch("app.models.event.EventRecord") as MockRecord:
            mock_instance = MagicMock()
            MockRecord.return_value = mock_instance
            await journal._append(entry)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_append_assigns_sequence(self) -> None:
        """追加时分配递增序列号。"""
        db = AsyncMock()
        journal = SQLAlchemyEventJournal(db)

        entry = _make_event_entry()
        with patch("app.models.event.EventRecord"):
            await journal._append(entry)
        # entry.sequence 应被赋值
        assert entry.sequence != 0 or initial_seq != 0


class TestEventJournalQuery:
    """_query 方法 — 事件查询。"""

    @pytest.mark.asyncio
    async def test_query_by_run_id(self) -> None:
        """按 run_id 过滤查询。"""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        journal = SQLAlchemyEventJournal(db)
        result = await journal._query(run_id="run-001")
        assert isinstance(result, list)
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_by_session_id(self) -> None:
        """按 session_id 过滤查询。"""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        journal = SQLAlchemyEventJournal(db)
        sid = uuid.uuid4()
        result = await journal._query(session_id=sid)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_with_limit(self) -> None:
        """limit 参数限制返回数量。"""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        journal = SQLAlchemyEventJournal(db)
        result = await journal._query(limit=10)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_empty_result(self) -> None:
        """无匹配事件时返回空列表。"""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        journal = SQLAlchemyEventJournal(db)
        result = await journal._query(run_id="nonexistent")
        assert result == []
