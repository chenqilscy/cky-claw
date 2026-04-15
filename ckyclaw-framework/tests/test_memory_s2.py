"""S2 记忆三类化测试 — 新增字段、count/search_by_tags、MemoryInjector、Runner 记忆注入。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ckyclaw_framework.memory.in_memory import InMemoryMemoryBackend
from ckyclaw_framework.memory.injector import MemoryInjectionConfig, MemoryInjector
from ckyclaw_framework.memory.memory import MemoryBackend, MemoryEntry, MemoryType

# ---------------------------------------------------------------------------
# MemoryEntry 新增字段
# ---------------------------------------------------------------------------


class TestMemoryEntryNewFields:
    """S2 新增 embedding / tags / access_count 字段。"""

    def test_defaults(self) -> None:
        """默认值：embedding=None, tags=[], access_count=0。"""
        entry = MemoryEntry()
        assert entry.embedding is None
        assert entry.tags == []
        assert entry.access_count == 0

    def test_custom_embedding(self) -> None:
        """自定义向量表示。"""
        vec = [0.1, 0.2, 0.3]
        entry = MemoryEntry(embedding=vec)
        assert entry.embedding == [0.1, 0.2, 0.3]

    def test_custom_tags(self) -> None:
        """自定义标签列表。"""
        entry = MemoryEntry(tags=["python", "async", "fastapi"])
        assert entry.tags == ["python", "async", "fastapi"]

    def test_custom_access_count(self) -> None:
        """自定义访问计数。"""
        entry = MemoryEntry(access_count=5)
        assert entry.access_count == 5

    def test_tags_not_shared(self) -> None:
        """不同实例的 tags 列表互不影响。"""
        a = MemoryEntry()
        b = MemoryEntry()
        a.tags.append("x")
        assert b.tags == []

    def test_all_new_fields_together(self) -> None:
        """同时设置所有新字段。"""
        entry = MemoryEntry(
            content="test",
            embedding=[1.0, 2.0],
            tags=["dev", "ops"],
            access_count=10,
        )
        assert entry.embedding == [1.0, 2.0]
        assert entry.tags == ["dev", "ops"]
        assert entry.access_count == 10
        assert entry.content == "test"


# ---------------------------------------------------------------------------
# MemoryBackend.count()
# ---------------------------------------------------------------------------


class TestMemoryBackendCount:
    """count() 方法返回用户条目总数。"""

    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.mark.asyncio
    async def test_count_empty(self, backend: InMemoryMemoryBackend) -> None:
        """空后端返回 0。"""
        assert await backend.count("u1") == 0

    @pytest.mark.asyncio
    async def test_count_single_user(self, backend: InMemoryMemoryBackend) -> None:
        """单用户多条目计数正确。"""
        for i in range(5):
            await backend.store("u1", MemoryEntry(id=f"e{i}", content=f"m{i}", user_id="u1"))
        assert await backend.count("u1") == 5

    @pytest.mark.asyncio
    async def test_count_user_isolation(self, backend: InMemoryMemoryBackend) -> None:
        """不同用户计数隔离。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1"))
        await backend.store("u1", MemoryEntry(id="e2", content="b", user_id="u1"))
        await backend.store("u2", MemoryEntry(id="e3", content="c", user_id="u2"))
        assert await backend.count("u1") == 2
        assert await backend.count("u2") == 1
        assert await backend.count("u3") == 0

    @pytest.mark.asyncio
    async def test_count_after_delete(self, backend: InMemoryMemoryBackend) -> None:
        """删除后计数更新。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1"))
        await backend.store("u1", MemoryEntry(id="e2", content="b", user_id="u1"))
        assert await backend.count("u1") == 2
        await backend.delete("e1")
        assert await backend.count("u1") == 1


# ---------------------------------------------------------------------------
# MemoryBackend.search_by_tags()
# ---------------------------------------------------------------------------


class TestSearchByTags:
    """search_by_tags() 按标签搜索记忆。"""

    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.mark.asyncio
    async def test_no_tags_returns_empty(self, backend: InMemoryMemoryBackend) -> None:
        """搜索空标签列表返回空。"""
        await backend.store("u1", MemoryEntry(id="e1", content="x", user_id="u1", tags=["a"]))
        result = await backend.search_by_tags("u1", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_tag_match(self, backend: InMemoryMemoryBackend) -> None:
        """单标签匹配。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1", tags=["python"]))
        await backend.store("u1", MemoryEntry(id="e2", content="b", user_id="u1", tags=["java"]))
        result = await backend.search_by_tags("u1", ["python"])
        assert len(result) == 1
        assert result[0].id == "e1"

    @pytest.mark.asyncio
    async def test_or_matching(self, backend: InMemoryMemoryBackend) -> None:
        """OR 匹配：含任一标签即命中。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1", tags=["python"]))
        await backend.store("u1", MemoryEntry(id="e2", content="b", user_id="u1", tags=["java"]))
        await backend.store("u1", MemoryEntry(id="e3", content="c", user_id="u1", tags=["rust"]))
        result = await backend.search_by_tags("u1", ["python", "java"])
        assert len(result) == 2
        ids = {r.id for r in result}
        assert ids == {"e1", "e2"}

    @pytest.mark.asyncio
    async def test_no_match(self, backend: InMemoryMemoryBackend) -> None:
        """无匹配标签返回空。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1", tags=["python"]))
        result = await backend.search_by_tags("u1", ["go"])
        assert result == []

    @pytest.mark.asyncio
    async def test_sorted_by_confidence(self, backend: InMemoryMemoryBackend) -> None:
        """结果按置信度降序排列。"""
        await backend.store("u1", MemoryEntry(
            id="e1", content="a", user_id="u1", tags=["dev"], confidence=0.5,
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", content="b", user_id="u1", tags=["dev"], confidence=0.9,
        ))
        await backend.store("u1", MemoryEntry(
            id="e3", content="c", user_id="u1", tags=["dev"], confidence=0.7,
        ))
        result = await backend.search_by_tags("u1", ["dev"])
        assert [r.id for r in result] == ["e2", "e3", "e1"]

    @pytest.mark.asyncio
    async def test_limit(self, backend: InMemoryMemoryBackend) -> None:
        """limit 参数限制返回数量。"""
        for i in range(10):
            await backend.store("u1", MemoryEntry(
                id=f"e{i}", content=f"m{i}", user_id="u1", tags=["common"],
            ))
        result = await backend.search_by_tags("u1", ["common"], limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_user_isolation(self, backend: InMemoryMemoryBackend) -> None:
        """标签搜索用户隔离。"""
        await backend.store("u1", MemoryEntry(id="e1", content="a", user_id="u1", tags=["py"]))
        await backend.store("u2", MemoryEntry(id="e2", content="b", user_id="u2", tags=["py"]))
        result = await backend.search_by_tags("u1", ["py"])
        assert len(result) == 1
        assert result[0].id == "e1"

    @pytest.mark.asyncio
    async def test_entry_with_multiple_tags(self, backend: InMemoryMemoryBackend) -> None:
        """条目有多标签时，任一匹配即命中。"""
        await backend.store("u1", MemoryEntry(
            id="e1", content="a", user_id="u1", tags=["python", "async", "web"],
        ))
        result = await backend.search_by_tags("u1", ["web"])
        assert len(result) == 1
        assert result[0].id == "e1"

    @pytest.mark.asyncio
    async def test_no_duplicate_results(self, backend: InMemoryMemoryBackend) -> None:
        """即使条目匹配多个搜索标签也不重复。"""
        await backend.store("u1", MemoryEntry(
            id="e1", content="a", user_id="u1", tags=["python", "async"],
        ))
        result = await backend.search_by_tags("u1", ["python", "async"])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# MemoryInjectionConfig
# ---------------------------------------------------------------------------


class TestMemoryInjectionConfig:
    """MemoryInjectionConfig 配置字段。"""

    def test_defaults(self) -> None:
        """默认值检查。"""
        cfg = MemoryInjectionConfig()
        assert cfg.max_memory_tokens == 1000
        assert cfg.min_confidence == 0.3
        assert cfg.inject_types is None
        assert cfg.max_entries == 20

    def test_custom_values(self) -> None:
        """自定义配置。"""
        cfg = MemoryInjectionConfig(
            max_memory_tokens=500,
            min_confidence=0.5,
            inject_types=[MemoryType.USER_PROFILE],
            max_entries=10,
        )
        assert cfg.max_memory_tokens == 500
        assert cfg.min_confidence == 0.5
        assert cfg.inject_types == [MemoryType.USER_PROFILE]
        assert cfg.max_entries == 10


# ---------------------------------------------------------------------------
# MemoryInjector
# ---------------------------------------------------------------------------


class TestMemoryInjector:
    """MemoryInjector 检索 + 格式化 + 注入。"""

    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.mark.asyncio
    async def test_build_context_empty_user_id(self, backend: InMemoryMemoryBackend) -> None:
        """空 user_id 返回空字符串。"""
        injector = MemoryInjector(backend)
        result = await injector.build_memory_context("", "query")
        assert result == ""

    @pytest.mark.asyncio
    async def test_build_context_no_matches(self, backend: InMemoryMemoryBackend) -> None:
        """无匹配记忆返回空字符串。"""
        await backend.store("u1", MemoryEntry(id="e1", content="Java 开发", user_id="u1"))
        injector = MemoryInjector(backend)
        result = await injector.build_memory_context("u1", "Python")
        assert result == ""

    @pytest.mark.asyncio
    async def test_build_context_with_matches(self, backend: InMemoryMemoryBackend) -> None:
        """匹配记忆格式化为 '## 用户记忆' 格式。"""
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE,
            content="喜欢 Python", user_id="u1", confidence=0.9,
        ))
        injector = MemoryInjector(backend)
        result = await injector.build_memory_context("u1", "Python")
        assert "## 用户记忆" in result
        assert "用户档案" in result
        assert "喜欢 Python" in result
        assert "0.90" in result

    @pytest.mark.asyncio
    async def test_filters_low_confidence(self, backend: InMemoryMemoryBackend) -> None:
        """过滤低置信度条目。"""
        await backend.store("u1", MemoryEntry(
            id="e1", content="Python 高", user_id="u1", confidence=0.8,
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", content="Python 低", user_id="u1", confidence=0.1,
        ))
        cfg = MemoryInjectionConfig(min_confidence=0.5)
        injector = MemoryInjector(backend, cfg)
        result = await injector.build_memory_context("u1", "Python")
        assert "Python 高" in result
        assert "Python 低" not in result

    @pytest.mark.asyncio
    async def test_filters_by_type(self, backend: InMemoryMemoryBackend) -> None:
        """按类型过滤注入。"""
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE,
            content="Python 档案", user_id="u1", confidence=0.9,
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", type=MemoryType.STRUCTURED_FACT,
            content="Python 事实", user_id="u1", confidence=0.9,
        ))
        cfg = MemoryInjectionConfig(inject_types=[MemoryType.USER_PROFILE])
        injector = MemoryInjector(backend, cfg)
        result = await injector.build_memory_context("u1", "Python")
        assert "Python 档案" in result
        assert "Python 事实" not in result

    @pytest.mark.asyncio
    async def test_respects_token_budget(self, backend: InMemoryMemoryBackend) -> None:
        """Token 预算限制注入量。"""
        for i in range(20):
            await backend.store("u1", MemoryEntry(
                id=f"e{i}",
                content=f"关键词 重复内容 item-{i} " * 10,
                user_id="u1",
                confidence=0.9,
            ))
        cfg = MemoryInjectionConfig(max_memory_tokens=50)  # ~150 chars
        injector = MemoryInjector(backend, cfg)
        result = await injector.build_memory_context("u1", "关键词")
        if result:
            lines = result.strip().split("\n")
            assert lines[0] == "## 用户记忆"
            # 受预算限制，不应包含全部 20 条
            assert len(lines) < 22

    @pytest.mark.asyncio
    async def test_search_exception_returns_empty(self) -> None:
        """后端搜索异常时安静返回空字符串。"""
        mock_backend = AsyncMock(spec=MemoryBackend)
        mock_backend.search.side_effect = RuntimeError("DB down")
        injector = MemoryInjector(mock_backend)
        result = await injector.build_memory_context("u1", "query")
        assert result == ""

    @pytest.mark.asyncio
    async def test_multiple_types_in_output(self, backend: InMemoryMemoryBackend) -> None:
        """多种类型在输出中正确标记。"""
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE,
            content="记忆搜索 档案", user_id="u1", confidence=0.9,
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", type=MemoryType.HISTORY_SUMMARY,
            content="记忆搜索 摘要", user_id="u1", confidence=0.8,
        ))
        await backend.store("u1", MemoryEntry(
            id="e3", type=MemoryType.STRUCTURED_FACT,
            content="记忆搜索 事实", user_id="u1", confidence=0.7,
        ))
        injector = MemoryInjector(backend)
        result = await injector.build_memory_context("u1", "记忆搜索")
        assert "用户档案" in result
        assert "历史摘要" in result
        assert "事实" in result


# ---------------------------------------------------------------------------
# RunConfig 记忆字段
# ---------------------------------------------------------------------------


class TestRunConfigMemoryFields:
    """RunConfig 的 memory_backend / memory_user_id / memory_injection_config 字段。"""

    def test_defaults_none(self) -> None:
        """默认值全部 None。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        cfg = RunConfig()
        assert cfg.memory_backend is None
        assert cfg.memory_user_id is None
        assert cfg.memory_injection_config is None

    def test_set_memory_fields(self) -> None:
        """设置记忆字段。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        backend = InMemoryMemoryBackend()
        inj_cfg = MemoryInjectionConfig(max_memory_tokens=500)
        cfg = RunConfig(
            memory_backend=backend,
            memory_user_id="user-123",
            memory_injection_config=inj_cfg,
        )
        assert cfg.memory_backend is backend
        assert cfg.memory_user_id == "user-123"
        assert cfg.memory_injection_config is inj_cfg
        assert cfg.memory_injection_config.max_memory_tokens == 500


# ---------------------------------------------------------------------------
# _build_system_messages 集成记忆注入
# ---------------------------------------------------------------------------


class TestBuildSystemMessagesMemoryInjection:
    """_build_system_messages 在配置记忆后端时注入记忆到 system 消息。"""

    @pytest.mark.asyncio
    async def test_no_memory_when_not_configured(self) -> None:
        """未配置 memory_backend 时不注入记忆。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        agent = Agent(name="test", instructions="Hello")
        config = RunConfig()
        ctx = RunContext(agent=agent, config=config)
        msgs = await _build_system_messages(agent, ctx, config)
        # 仅包含 instructions
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_no_memory_when_no_user_id(self) -> None:
        """未设置 memory_user_id 时不注入记忆。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(id="e1", content="test", user_id="u1"))

        agent = Agent(name="test", instructions="Hello")
        config = RunConfig(memory_backend=backend)
        ctx = RunContext(agent=agent, config=config)
        msgs = await _build_system_messages(agent, ctx, config)
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_injects_memory_with_query(self) -> None:
        """配置完整时注入匹配记忆。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import Message, MessageRole
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE,
            content="用户偏好 Python", user_id="u1", confidence=0.9,
        ))

        agent = Agent(name="test", instructions="Help the user")
        config = RunConfig(memory_backend=backend, memory_user_id="u1")
        ctx = RunContext(agent=agent, config=config)

        # 提供用户消息作为 query 来源
        user_msgs = [Message(role=MessageRole.USER, content="用户偏好")]
        msgs = await _build_system_messages(agent, ctx, config, user_msgs)

        # 应该有 memory + instructions = 2 条
        assert len(msgs) == 2
        memory_msg = msgs[0]
        assert "用户记忆" in memory_msg.content
        assert "用户偏好 Python" in memory_msg.content
        instructions_msg = msgs[1]
        assert instructions_msg.content == "Help the user"

    @pytest.mark.asyncio
    async def test_memory_between_prefix_and_instructions(self) -> None:
        """记忆消息位于 cache prefix 和 instructions 之间。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import Message, MessageRole
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(
            id="e1", type=MemoryType.USER_PROFILE,
            content="记忆测试内容", user_id="u1", confidence=0.9,
        ))

        agent = Agent(name="test", instructions="Instructions here")
        config = RunConfig(
            system_prompt_prefix="Global prefix",
            memory_backend=backend,
            memory_user_id="u1",
        )
        ctx = RunContext(agent=agent, config=config)

        user_msgs = [Message(role=MessageRole.USER, content="记忆测试内容")]
        msgs = await _build_system_messages(agent, ctx, config, user_msgs)

        # cache prefix + memory + instructions = 3 条
        assert len(msgs) == 3
        assert msgs[0].content == "Global prefix"
        assert "cache_control" in msgs[0].metadata
        assert "用户记忆" in msgs[1].content
        assert msgs[2].content == "Instructions here"

    @pytest.mark.asyncio
    async def test_no_memory_when_no_match(self) -> None:
        """无匹配记忆时不注入记忆消息。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import Message, MessageRole
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(
            id="e1", content="Java 相关", user_id="u1", confidence=0.9,
        ))

        agent = Agent(name="test", instructions="Hello")
        config = RunConfig(memory_backend=backend, memory_user_id="u1")
        ctx = RunContext(agent=agent, config=config)

        user_msgs = [Message(role=MessageRole.USER, content="Python 问题")]
        msgs = await _build_system_messages(agent, ctx, config, user_msgs)

        # Java 不匹配 Python，只有 instructions
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_memory_with_empty_messages(self) -> None:
        """空消息列表时 query 为空字符串，不匹配。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(
            id="e1", content="test", user_id="u1", confidence=0.9,
        ))

        agent = Agent(name="test", instructions="Hello")
        config = RunConfig(memory_backend=backend, memory_user_id="u1")
        ctx = RunContext(agent=agent, config=config)

        msgs = await _build_system_messages(agent, ctx, config, [])
        # 空 query 不匹配，只有 instructions
        assert len(msgs) == 1

    @pytest.mark.asyncio
    async def test_memory_injection_config_respected(self) -> None:
        """MemoryInjectionConfig 的 min_confidence 被尊重。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import Message, MessageRole
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        backend = InMemoryMemoryBackend()
        await backend.store("u1", MemoryEntry(
            id="e1", content="低信 Python", user_id="u1", confidence=0.2,
        ))
        await backend.store("u1", MemoryEntry(
            id="e2", content="高信 Python", user_id="u1", confidence=0.9,
        ))

        agent = Agent(name="test", instructions="Hello")
        inj_cfg = MemoryInjectionConfig(min_confidence=0.5)
        config = RunConfig(
            memory_backend=backend,
            memory_user_id="u1",
            memory_injection_config=inj_cfg,
        )
        ctx = RunContext(agent=agent, config=config)

        user_msgs = [Message(role=MessageRole.USER, content="Python")]
        msgs = await _build_system_messages(agent, ctx, config, user_msgs)

        # 应注入记忆（只有高信 Python）
        assert len(msgs) == 2
        memory_content = msgs[0].content
        assert "高信 Python" in memory_content
        assert "低信 Python" not in memory_content


# ---------------------------------------------------------------------------
# InMemoryMemoryBackend 存储 tags / embedding
# ---------------------------------------------------------------------------


class TestInMemoryBackendNewFields:
    """InMemoryMemoryBackend 正确持久化新字段。"""

    @pytest.fixture
    def backend(self) -> InMemoryMemoryBackend:
        return InMemoryMemoryBackend()

    @pytest.mark.asyncio
    async def test_store_preserves_tags(self, backend: InMemoryMemoryBackend) -> None:
        """存储后取回 tags 不丢失。"""
        entry = MemoryEntry(id="e1", content="x", user_id="u1", tags=["a", "b"])
        await backend.store("u1", entry)
        result = await backend.get("e1")
        assert result is not None
        assert result.tags == ["a", "b"]

    @pytest.mark.asyncio
    async def test_store_preserves_embedding(self, backend: InMemoryMemoryBackend) -> None:
        """存储后取回 embedding 不丢失。"""
        vec = [0.1, 0.2, 0.3, 0.4]
        entry = MemoryEntry(id="e1", content="x", user_id="u1", embedding=vec)
        await backend.store("u1", entry)
        result = await backend.get("e1")
        assert result is not None
        assert result.embedding == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_store_preserves_access_count(self, backend: InMemoryMemoryBackend) -> None:
        """存储后取回 access_count 不丢失。"""
        entry = MemoryEntry(id="e1", content="x", user_id="u1", access_count=42)
        await backend.store("u1", entry)
        result = await backend.get("e1")
        assert result is not None
        assert result.access_count == 42

    @pytest.mark.asyncio
    async def test_upsert_preserves_new_fields(self, backend: InMemoryMemoryBackend) -> None:
        """upsert 更新后新字段正确保留。"""
        entry1 = MemoryEntry(id="e1", content="v1", user_id="u1", tags=["old"], access_count=1)
        await backend.store("u1", entry1)

        entry2 = MemoryEntry(id="e1", content="v2", user_id="u1", tags=["new"], access_count=5)
        await backend.store("u1", entry2)

        result = await backend.get("e1")
        assert result is not None
        assert result.content == "v2"
        assert result.tags == ["new"]
        assert result.access_count == 5
