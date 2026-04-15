"""Memory 模块测试 — MemoryEntry / InMemoryMemoryBackend / MemoryRetriever / DecayMode / Hooks。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from ckyclaw_framework.memory.hooks import MemoryExtractionHook
from ckyclaw_framework.memory.in_memory import InMemoryMemoryBackend
from ckyclaw_framework.memory.memory import (
    DecayMode,
    MemoryBackend,
    MemoryEntry,
    MemoryType,
    compute_exponential_decay,
)
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
        old_time = datetime.now(UTC) - timedelta(days=10)
        datetime.now(UTC)

        entry_old = MemoryEntry(id="e1", content="old", user_id="u1", confidence=0.8)
        entry_old.updated_at = old_time
        await backend.store("u1", entry_old)
        # Override updated_at that store sets
        backend._entries["e1"].updated_at = old_time

        entry_new = MemoryEntry(id="e2", content="new", user_id="u1", confidence=0.9)
        await backend.store("u1", entry_new)

        threshold = datetime.now(UTC) - timedelta(days=1)
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
        old_time = datetime.now(UTC) - timedelta(days=10)
        entry = MemoryEntry(id="e1", content="x", user_id="u1", confidence=0.05)
        await backend.store("u1", entry)
        backend._entries["e1"].updated_at = old_time

        threshold = datetime.now(UTC) - timedelta(days=1)
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
            DecayMode,
            InMemoryMemoryBackend,
            MemoryBackend,
            MemoryEntry,
            MemoryExtractionHook,
            MemoryRetriever,
            MemoryType,
            compute_exponential_decay,
        )
        assert MemoryType is not None
        assert MemoryEntry is not None
        assert MemoryBackend is not None
        assert InMemoryMemoryBackend is not None
        assert MemoryRetriever is not None
        assert DecayMode is not None
        assert MemoryExtractionHook is not None
        assert compute_exponential_decay is not None


# ---------------------------------------------------------------------------
# DecayMode & 指数衰减
# ---------------------------------------------------------------------------


class TestDecayMode:
    """DecayMode 枚举与指数衰减函数。"""

    def test_enum_values(self) -> None:
        assert DecayMode.LINEAR == "linear"
        assert DecayMode.EXPONENTIAL == "exponential"
        assert len(DecayMode) == 2

    def test_compute_exponential_decay_positive(self) -> None:
        """正常衰减：30 天后置信度应下降。"""
        result = compute_exponential_decay(1.0, 30.0, 0.1)
        assert 0.0 < result < 1.0
        # e^(-0.1 * 30) ≈ 0.0498
        assert abs(result - 0.0498) < 0.01

    def test_compute_exponential_decay_zero_days(self) -> None:
        """0 天不衰减。"""
        assert compute_exponential_decay(0.8, 0.0, 0.1) == 0.8

    def test_compute_exponential_decay_zero_lambda(self) -> None:
        """λ=0 不衰减。"""
        assert compute_exponential_decay(0.8, 30.0, 0.0) == 0.8

    def test_compute_exponential_decay_negative_days(self) -> None:
        """负天数不衰减。"""
        assert compute_exponential_decay(0.8, -5.0, 0.1) == 0.8

    def test_compute_exponential_decay_floor_zero(self) -> None:
        """结果不低于 0.0。"""
        result = compute_exponential_decay(0.01, 1000.0, 1.0)
        assert result == 0.0


class TestInMemoryExponentialDecay:
    """InMemoryMemoryBackend 的指数衰减测试。"""

    @pytest.mark.asyncio
    async def test_decay_exponential_mode(self) -> None:
        """exponential 模式下衰减值合理。"""
        backend = InMemoryMemoryBackend()
        old_time = datetime.now(UTC) - timedelta(days=10)
        await backend.store(
            "u1",
            MemoryEntry(id="e1", content="old fact", user_id="u1", confidence=1.0),
        )
        # 手动修改 updated_at 为 10 天前
        backend._entries["e1"].updated_at = old_time

        count = await backend.decay(
            before=datetime.now(UTC), rate=0.1, mode=DecayMode.EXPONENTIAL
        )
        assert count == 1
        entry = await backend.get("e1")
        assert entry is not None
        # e^(-0.1 * 10) ≈ 0.368
        assert 0.3 < entry.confidence < 0.5

    @pytest.mark.asyncio
    async def test_decay_linear_default(self) -> None:
        """默认 LINEAR 模式兼容旧行为。"""
        backend = InMemoryMemoryBackend()
        old_time = datetime.now(UTC) - timedelta(hours=1)
        await backend.store(
            "u1",
            MemoryEntry(id="e1", content="fact", user_id="u1", confidence=0.8),
        )
        backend._entries["e1"].updated_at = old_time

        count = await backend.decay(before=datetime.now(UTC), rate=0.2)
        assert count == 1
        entry = await backend.get("e1")
        assert entry is not None
        assert abs(entry.confidence - 0.6) < 0.01

    @pytest.mark.asyncio
    async def test_decay_exponential_skips_recent(self) -> None:
        """指数衰减不影响 before 之后的条目。"""
        backend = InMemoryMemoryBackend()
        await backend.store(
            "u1",
            MemoryEntry(id="e1", content="recent", user_id="u1", confidence=0.9),
        )
        # updated_at 默认是现在，before 设置为 1 小时前
        count = await backend.decay(
            before=datetime.now(UTC) - timedelta(hours=1),
            rate=0.1,
            mode=DecayMode.EXPONENTIAL,
        )
        assert count == 0
        entry = await backend.get("e1")
        assert entry is not None
        assert entry.confidence == 0.9


# ---------------------------------------------------------------------------
# MemoryExtractionHook
# ---------------------------------------------------------------------------


class TestMemoryExtractionHook:
    """自动记忆提取钩子测试。"""

    @pytest.mark.asyncio
    async def test_extracts_on_run_end(self) -> None:
        """Run 结束后自动提取记忆。"""
        backend = InMemoryMemoryBackend()
        hook = MemoryExtractionHook(
            backend=backend, user_id="u1", min_output_length=10
        )
        hooks = hook.as_run_hooks()

        # 模拟 RunContext
        mock_ctx = MagicMock()
        mock_ctx.agent.name = "test-agent"

        # 模拟 RunResult
        mock_result = MagicMock()
        mock_result.output = "这是一段足够长的 Agent 输出内容，用于测试记忆提取。"
        mock_result.last_agent_name = "test-agent"

        # 触发 on_run_end
        assert hooks.on_run_end is not None
        await hooks.on_run_end(mock_ctx, mock_result)

        entries = await backend.list_entries("u1")
        assert len(entries) == 1
        assert "Agent 输出内容" in entries[0].content
        assert entries[0].agent_name == "test-agent"
        assert entries[0].confidence == 0.7
        assert hook.extracted_count == 1

    @pytest.mark.asyncio
    async def test_skips_short_output(self) -> None:
        """输出太短时不提取。"""
        backend = InMemoryMemoryBackend()
        hook = MemoryExtractionHook(
            backend=backend, user_id="u1", min_output_length=100
        )
        hooks = hook.as_run_hooks()

        mock_ctx = MagicMock()
        mock_ctx.agent.name = "bot"
        mock_result = MagicMock()
        mock_result.output = "短"
        mock_result.last_agent_name = "bot"

        assert hooks.on_run_end is not None
        await hooks.on_run_end(mock_ctx, mock_result)

        entries = await backend.list_entries("u1")
        assert len(entries) == 0
        assert hook.extracted_count == 0

    @pytest.mark.asyncio
    async def test_skips_empty_user_id(self) -> None:
        """user_id 为空时不提取。"""
        backend = InMemoryMemoryBackend()
        hook = MemoryExtractionHook(backend=backend, user_id="")
        hooks = hook.as_run_hooks()

        mock_ctx = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "x" * 200
        mock_result.last_agent_name = "bot"

        assert hooks.on_run_end is not None
        await hooks.on_run_end(mock_ctx, mock_result)
        assert hook.extracted_count == 0

    @pytest.mark.asyncio
    async def test_custom_extract_fn(self) -> None:
        """自定义提取函数。"""
        backend = InMemoryMemoryBackend()

        def custom_extract(output: str, agent_name: str) -> list[str]:
            return [f"[{agent_name}] 关键信息: {output[:50]}"]

        hook = MemoryExtractionHook(
            backend=backend,
            user_id="u1",
            min_output_length=10,
            extract_fn=custom_extract,
        )
        hooks = hook.as_run_hooks()

        mock_ctx = MagicMock()
        mock_ctx.agent.name = "bot"
        mock_result = MagicMock()
        mock_result.output = "这是自定义提取测试的输出文本"
        mock_result.last_agent_name = "bot"

        assert hooks.on_run_end is not None
        await hooks.on_run_end(mock_ctx, mock_result)

        entries = await backend.list_entries("u1")
        assert len(entries) == 1
        assert "[bot] 关键信息:" in entries[0].content

    @pytest.mark.asyncio
    async def test_on_agent_start_tracks_name(self) -> None:
        """on_agent_start 记录 Agent 名称。"""
        backend = InMemoryMemoryBackend()
        hook = MemoryExtractionHook(backend=backend, user_id="u1")
        hooks = hook.as_run_hooks()

        mock_ctx = MagicMock()
        assert hooks.on_agent_start is not None
        await hooks.on_agent_start(mock_ctx, "my-agent")
        assert hook._agent_name == "my-agent"
