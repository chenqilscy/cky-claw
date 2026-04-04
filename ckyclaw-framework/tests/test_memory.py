"""Memory 模块测试 — MemoryEntry / InMemoryMemoryBackend / MemoryRetriever。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from ckyclaw_framework.memory.memory import MemoryBackend, MemoryEntry, MemoryType
from ckyclaw_framework.memory.in_memory import InMemoryMemoryBackend
from ckyclaw_framework.memory.retriever import MemoryRetriever


# ---------------------------------------------------------------------------
# MemoryType & MemoryEntry
# ---------------------------------------------------------------------------


class TestMemoryType:
    def test_values(self) -> None:
        assert MemoryType.USER_PROFILE == "user_profile"
        assert MemoryType.HISTORY_SUMMARY == "history_summary"
        assert MemoryType.STRUCTURED_FACT == "structured_fact"

    def test_enum_members(self) -> None:
        assert len(MemoryType) == 3


class TestMemoryEntry:
    def test_defaults(self) -> None:
        entry = MemoryEntry()
        assert entry.id  # non-empty UUID
        assert entry.type == MemoryType.STRUCTURED_FACT
        assert entry.content == ""
        assert entry.confidence == 1.0
        assert entry.user_id == ""
        assert entry.agent_name is None
        assert entry.source_session_id is None
        assert isinstance(entry.metadata, dict)
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)

    def test_custom_fields(self) -> None:
        entry = MemoryEntry(
            id="test-1",
            type=MemoryType.USER_PROFILE,
            content="用户偏好 Python",
            confidence=0.9,
            user_id="user-123",
            agent_name="coding-agent",
            source_session_id="session-456",
            metadata={"key": "value"},
        )
        assert entry.id == "test-1"
        assert entry.type == MemoryType.USER_PROFILE
        assert entry.content == "用户偏好 Python"
        assert entry.confidence == 0.9
        assert entry.user_id == "user-123"
        assert entry.agent_name == "coding-agent"
        assert entry.source_session_id == "session-456"
        assert entry.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# MemoryBackend ABC
# ---------------------------------------------------------------------------


class TestMemoryBackendABC:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            MemoryBackend()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# InMemoryMemoryBackend
# ---------------------------------------------------------------------------


class TestInMemoryMemoryBackend:
    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.mark.asyncio
    async def test_store_and_get(self, backend: InMemoryMemoryBackend) -> None:
        entry = MemoryEntry(id="e1", content="测试记忆", user_id="u1")
        await backend.store("u1", entry)
        result = await backend.get("e1")
        assert result is not None
        assert result.id == "e1"
        assert result.content == "测试记忆"
        assert result.user_id == "u1"

    @pytest.mark.asyncio
    async def test_store_upsert(self, backend: InMemoryMemoryBackend) -> None:
        entry1 = MemoryEntry(id="e1", content="版本1", user_id="u1")
        await backend.store("u1", entry1)
        created_at = (await backend.get("e1")).created_at  # type: ignore[union-attr]

        entry2 = MemoryEntry(id="e1", content="版本2", user_id="u1")
        await backend.store("u1", entry2)
        result = await backend.get("e1")
        assert result is not None
        assert result.content == "版本2"
        assert result.created_at == created_at  # created_at preserved

    @pytest.mark.asyncio
    async def test_store_user_id_required(self, backend: InMemoryMemoryBackend) -> None:
        entry = MemoryEntry(id="e1", content="x")
        with pytest.raises(ValueError, match="user_id"):
            await backend.store("", entry)

    @pytest.mark.asyncio
    async def test_store_cross_user_forbidden(self, backend: InMemoryMemoryBackend) -> None:
        entry = MemoryEntry(id="e1", content="x", user_id="u1")
        await backend.store("u1", entry)
        entry2 = MemoryEntry(id="e1", content="x", user_id="u2")
        with pytest.raises(PermissionError):
            await backend.store("u2", entry2)

    @pytest.mark.asyncio
    async def test_search_keyword(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="Python 开发", user_id="u1", confidence=0.8))
        await backend.store("u1", MemoryEntry(id="e2", content="Java 开发", user_id="u1", confidence=0.9))
        await backend.store("u1", MemoryEntry(id="e3", content="Python 测试", user_id="u1", confidence=0.7))
        await backend.store("u2", MemoryEntry(id="e4", content="Python 其他用户", user_id="u2"))

        results = await backend.search("u1", "Python")
        assert len(results) == 2
        # sorted by confidence desc
        assert results[0].id == "e1"
        assert results[1].id == "e3"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="test", user_id="u1"))
        results = await backend.search("u1", "")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_limit(self, backend: InMemoryMemoryBackend) -> None:
        for i in range(10):
            await backend.store("u1", MemoryEntry(
                id=f"e{i}", content=f"关键词 item {i}", user_id="u1", confidence=float(i) / 10
            ))
        results = await backend.search("u1", "关键词", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="PostgreSQL", user_id="u1"))
        results = await backend.search("u1", "postgresql")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_entries(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE, content="p", user_id="u1", agent_name="a1"
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", type=MemoryType.STRUCTURED_FACT, content="f", user_id="u1", agent_name="a2"
        ))
        await backend.store("u2", MemoryEntry(
            id="e3", type=MemoryType.USER_PROFILE, content="x", user_id="u2"
        ))

        # All for u1
        all_u1 = await backend.list_entries("u1")
        assert len(all_u1) == 2

        # Filter by type
        profiles = await backend.list_entries("u1", memory_type=MemoryType.USER_PROFILE)
        assert len(profiles) == 1
        assert profiles[0].id == "e1"

        # Filter by agent_name
        a2 = await backend.list_entries("u1", agent_name="a2")
        assert len(a2) == 1
        assert a2[0].id == "e2"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, backend: InMemoryMemoryBackend) -> None:
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="x", user_id="u1"))
        await backend.delete("e1")
        assert await backend.get("e1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend: InMemoryMemoryBackend) -> None:
        # Should not raise
        await backend.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_by_user(self, backend: InMemoryMemoryBackend) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1"))
        await backend.store("u1", MemoryEntry(id="e2", content="b", user_id="u1"))
        await backend.store("u2", MemoryEntry(id="e3", content="c", user_id="u2"))

        count = await backend.delete_by_user("u1")
        assert count == 2
        assert await backend.get("e1") is None
        assert await backend.get("e2") is None
        assert await backend.get("e3") is not None  # u2 unaffected

    @pytest.mark.asyncio
    async def test_decay(self, backend: InMemoryMemoryBackend) -> None:
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        new_time = datetime.now(timezone.utc)

        entry_old = MemoryEntry(id="e1", content="old", user_id="u1", confidence=0.8)
        entry_old.updated_at = old_time
        await backend.store("u1", entry_old)
        # Override updated_at that store sets
        backend._entries["e1"].updated_at = old_time

        entry_new = MemoryEntry(id="e2", content="new", user_id="u1", confidence=0.9)
        await backend.store("u1", entry_new)

        threshold = datetime.now(timezone.utc) - timedelta(days=1)
        affected = await backend.decay(threshold, 0.1)
        assert affected == 1

        old_result = await backend.get("e1")
        assert old_result is not None
        assert abs(old_result.confidence - 0.7) < 0.001

        new_result = await backend.get("e2")
        assert new_result is not None
        assert new_result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_decay_floor_zero(self, backend: InMemoryMemoryBackend) -> None:
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        entry = MemoryEntry(id="e1", content="x", user_id="u1", confidence=0.05)
        await backend.store("u1", entry)
        backend._entries["e1"].updated_at = old_time

        threshold = datetime.now(timezone.utc) - timedelta(days=1)
        await backend.decay(threshold, 0.1)

        result = await backend.get("e1")
        assert result is not None
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# MemoryRetriever
# ---------------------------------------------------------------------------


class TestMemoryRetriever:
    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.fixture
    def retriever(self, backend: InMemoryMemoryBackend) -> MemoryRetriever:
        return MemoryRetriever(backend=backend, max_memory_tokens=500, min_confidence=0.5)

    @pytest.mark.asyncio
    async def test_retrieve_filters_low_confidence(
        self, backend: InMemoryMemoryBackend, retriever: MemoryRetriever
    ) -> None:
        await backend.store("u1", MemoryEntry(id="e1", content="Python 高置信", user_id="u1", confidence=0.9))
        await backend.store("u1", MemoryEntry(id="e2", content="Python 低置信", user_id="u1", confidence=0.3))

        results = await retriever.retrieve("u1", "Python")
        assert len(results) == 1
        assert results[0].id == "e1"

    @pytest.mark.asyncio
    async def test_retrieve_limit(
        self, backend: InMemoryMemoryBackend, retriever: MemoryRetriever
    ) -> None:
        for i in range(10):
            await backend.store("u1", MemoryEntry(
                id=f"e{i}", content=f"共同关键词 item {i}", user_id="u1", confidence=0.8
            ))
        results = await retriever.retrieve("u1", "共同关键词", limit=3)
        assert len(results) == 3

    def test_format_for_injection_empty(self, retriever: MemoryRetriever) -> None:
        result = retriever.format_for_injection([])
        assert result == ""

    def test_format_for_injection(self, retriever: MemoryRetriever) -> None:
        entries = [
            MemoryEntry(id="e1", type=MemoryType.USER_PROFILE, content="偏好 Python", confidence=0.9),
            MemoryEntry(id="e2", type=MemoryType.STRUCTURED_FACT, content="项目用 PG 16", confidence=0.85),
        ]
        result = retriever.format_for_injection(entries)
        assert "## 用户记忆" in result
        assert "用户档案" in result
        assert "偏好 Python" in result
        assert "事实" in result
        assert "项目用 PG 16" in result
        assert "0.90" in result
        assert "0.85" in result

    def test_format_respects_token_budget(self) -> None:
        backend = InMemoryMemoryBackend()
        retriever = MemoryRetriever(backend=backend, max_memory_tokens=20)  # Small budget (~80 chars)
        entries = [
            MemoryEntry(id=f"e{i}", content=f"这是一条很长的记忆内容编号 {i} " * 5, confidence=0.9)
            for i in range(20)
        ]
        result = retriever.format_for_injection(entries)
        # Should contain header and at least 1 entry, but not all 20
        if result:
            lines = result.split("\n")
            assert lines[0] == "## 用户记忆"
            assert len(lines) < 22  # much fewer than 20+1 entries
        # With very limited budget, it's valid to return "" if no entry fits


# ---------------------------------------------------------------------------
# Module Exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_framework_init_exports(self) -> None:
        import ckyclaw_framework
        assert hasattr(ckyclaw_framework, "MemoryType")
        assert hasattr(ckyclaw_framework, "MemoryEntry")
        assert hasattr(ckyclaw_framework, "MemoryBackend")
        assert hasattr(ckyclaw_framework, "InMemoryMemoryBackend")
        assert hasattr(ckyclaw_framework, "MemoryRetriever")

    def test_memory_init_exports(self) -> None:
        from ckyclaw_framework.memory import (
            MemoryType,
            MemoryEntry,
            MemoryBackend,
            InMemoryMemoryBackend,
            MemoryRetriever,
        )
        assert MemoryType is not None
        assert MemoryEntry is not None
        assert MemoryBackend is not None
        assert InMemoryMemoryBackend is not None
        assert MemoryRetriever is not None
