"""S1 上下文工程测试 — PROGRESSIVE 策略 + Artifact 外部化 + 工具结果截断。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.artifacts.store import InMemoryArtifactStore, _estimate_token_count
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.session.history_trimmer import (
    HistoryTrimConfig,
    HistoryTrimStrategy,
    HistoryTrimmer,
)


def _make_msg(
    role: MessageRole,
    content: str,
    tokens: int | None = None,
    tool_call_id: str | None = None,
    agent_name: str | None = None,
) -> Message:
    """创建测试 Message。"""
    return Message(
        role=role,
        content=content,
        token_usage=TokenUsage(tokens or 0, 0, tokens or 0) if tokens else None,
        tool_call_id=tool_call_id,
        agent_name=agent_name,
    )


# ── PROGRESSIVE 策略测试 ──────────────────────────────────────────


class TestProgressiveStrategy:
    """PROGRESSIVE 分级递进裁剪策略。"""

    def test_progressive_fits_budget_no_compression(self) -> None:
        """消息在 TOKEN_BUDGET 内不压缩时 PROGRESSIVE 直接返回。"""
        msgs = [
            _make_msg(MessageRole.USER, "hello", tokens=10),
            _make_msg(MessageRole.ASSISTANT, "hi!", tokens=5),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=100,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 2
        assert result[0].content == "hello"
        assert result[1].content == "hi!"

    def test_progressive_phase1_sufficient(self) -> None:
        """Phase 1 TOKEN_BUDGET 裁剪已保留 >=50% 非系统消息 → 不进入 Phase 2。"""
        msgs = [
            _make_msg(MessageRole.USER, "a" * 90, tokens=30),
            _make_msg(MessageRole.ASSISTANT, "b" * 90, tokens=30),
            _make_msg(MessageRole.USER, "c" * 90, tokens=30),
            _make_msg(MessageRole.ASSISTANT, "d" * 90, tokens=30),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=80,  # 能装 2-3 条
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 保留了 >=50% (2/4)，不会触发 Phase2
        assert len(result) >= 2

    def test_progressive_phase2_compresses_tool_results(self) -> None:
        """Phase 2 压缩长工具结果后在同等预算下保留更多轮次。"""
        # 构造 6 条消息，其中 2 条 tool 结果很长
        msgs = [
            _make_msg(MessageRole.USER, "query1", tokens=10),
            _make_msg(MessageRole.ASSISTANT, "calling tool", tokens=10),
            _make_msg(MessageRole.TOOL, "X" * 3000, tokens=1000, tool_call_id="t1", agent_name="big_tool"),
            _make_msg(MessageRole.ASSISTANT, "got result", tokens=10),
            _make_msg(MessageRole.USER, "query2", tokens=10),
            _make_msg(MessageRole.ASSISTANT, "final answer", tokens=10),
        ]
        # TOKEN_BUDGET = 200: Phase 1 只保留 1-2 最新消息 (<50%)，触发 Phase 2
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=200,
            progressive_tool_result_limit=100,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # Phase 2 把 3000 字符工具结果压缩到 ~100 字符，节省大量 token
        # 应该能保留更多消息
        assert len(result) >= 3

        # 验证 tool 消息被压缩了
        tool_msgs = [m for m in result if m.role == MessageRole.TOOL]
        for tool_msg in tool_msgs:
            assert len(tool_msg.content) <= 200  # 100 + "... [truncated]"

    def test_progressive_preserves_system_messages(self) -> None:
        """PROGRESSIVE 保留 system 消息。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "system instructions", tokens=20),
            _make_msg(MessageRole.USER, "query", tokens=10),
            _make_msg(MessageRole.TOOL, "X" * 3000, tokens=1000, tool_call_id="t1"),
            _make_msg(MessageRole.ASSISTANT, "answer", tokens=10),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=100,
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        system_msgs = [m for m in result if m.role == MessageRole.SYSTEM]
        assert len(system_msgs) == 1
        assert system_msgs[0].content == "system instructions"

    def test_progressive_empty_messages(self) -> None:
        """空消息列表返回空。"""
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.PROGRESSIVE)
        result = HistoryTrimmer.trim([], config)
        assert result == []

    def test_progressive_no_tool_messages(self) -> None:
        """没有工具消息时 Phase 2 不改变结果。"""
        msgs = [
            _make_msg(MessageRole.USER, "a" * 600, tokens=200),
            _make_msg(MessageRole.ASSISTANT, "b" * 600, tokens=200),
            _make_msg(MessageRole.USER, "c" * 90, tokens=30),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=60,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 只有最新的 30 token 消息能装下
        assert len(result) >= 1

    def test_progressive_with_custom_tool_result_limit(self) -> None:
        """自定义 progressive_tool_result_limit。"""
        msgs = [
            _make_msg(MessageRole.USER, "q", tokens=5),
            _make_msg(MessageRole.TOOL, "R" * 2000, tokens=666, tool_call_id="t1"),
            _make_msg(MessageRole.ASSISTANT, "a", tokens=5),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.PROGRESSIVE,
            max_history_tokens=50,
            progressive_tool_result_limit=50,
        )
        result = HistoryTrimmer.trim(msgs, config)
        tool_msgs = [m for m in result if m.role == MessageRole.TOOL]
        for m in tool_msgs:
            # 应该被压缩到 ~50 + "... [truncated]" 长度
            assert len(m.content) <= 80


# ── RunConfig Artifact 字段测试 ──────────────────────────────────


class TestRunConfigArtifactFields:
    """RunConfig 新增字段默认值。"""

    def test_default_values(self) -> None:
        """RunConfig 默认 artifact_store=None, artifact_threshold=5000, max_tool_result_chars=None。"""
        from ckyclaw_framework.runner.run_config import RunConfig

        config = RunConfig()
        assert config.artifact_store is None
        assert config.artifact_threshold == 5000
        assert config.max_tool_result_chars is None

    def test_custom_values(self) -> None:
        """可自定义 artifact 相关字段。"""
        from ckyclaw_framework.runner.run_config import RunConfig

        store = InMemoryArtifactStore()
        config = RunConfig(
            artifact_store=store,
            artifact_threshold=1000,
            max_tool_result_chars=2000,
        )
        assert config.artifact_store is store
        assert config.artifact_threshold == 1000
        assert config.max_tool_result_chars == 2000


# ── Artifact 外部化集成测试 ──────────────────────────────────────


class TestArtifactExternalization:
    """Runner Artifact 外部化逻辑（单元级模拟）。"""

    @pytest.mark.asyncio
    async def test_tool_result_externalized_when_exceeding_threshold(self) -> None:
        """工具结果超过 artifact_threshold 时被外部化到 ArtifactStore。"""
        store = InMemoryArtifactStore()
        big_result = "X" * 30000  # ~10000 tokens, 远超 5000 阈值

        # 模拟 Runner 中的外部化逻辑
        threshold = 5000
        if _estimate_token_count(big_result) > threshold:
            artifact = await store.save(
                run_id="test-run",
                content=big_result,
                metadata={"tool_name": "big_tool", "tool_call_id": "tc1"},
            )
            externalized = (
                f"[Artifact {artifact.artifact_id}] {artifact.summary}\n"
                f"(Full content externalized, {artifact.token_count} tokens)"
            )
        else:
            externalized = big_result

        # 验证外部化后上下文消息变小
        assert len(externalized) < len(big_result)
        assert "Artifact" in externalized
        assert "truncated" in artifact.summary

        # 验证原始内容可从 store 恢复
        loaded = await store.load(artifact.artifact_id)
        assert loaded is not None
        assert loaded.content == big_result

    @pytest.mark.asyncio
    async def test_small_result_not_externalized(self) -> None:
        """工具结果未超过阈值时不外部化。"""
        store = InMemoryArtifactStore()
        small_result = "OK"

        threshold = 5000
        if _estimate_token_count(small_result) > threshold:
            artifact = await store.save(run_id="test-run", content=small_result)
            result = f"[Artifact {artifact.artifact_id}] {artifact.summary}"
        else:
            result = small_result

        assert result == "OK"
        artifacts = await store.list_by_run("test-run")
        assert len(artifacts) == 0


# ── 工具结果硬截断测试 ──────────────────────────────────────────


class TestToolResultTruncation:
    """max_tool_result_chars 硬截断逻辑。"""

    def test_truncate_long_result(self) -> None:
        """超过 max_tool_result_chars 时截断。"""
        result = "A" * 5000
        max_chars = 1000
        if len(result) > max_chars:
            result = result[:max_chars] + "... [truncated]"
        assert len(result) == 1000 + len("... [truncated]")
        assert result.endswith("... [truncated]")

    def test_no_truncate_when_within_limit(self) -> None:
        """未超过 max_tool_result_chars 时不截断。"""
        result = "short result"
        max_chars = 1000
        if len(result) > max_chars:
            result = result[:max_chars] + "... [truncated]"
        assert result == "short result"

    def test_truncate_after_artifact_externalization(self) -> None:
        """截断在 Artifact 外部化之后生效（先外部化再截断兜底）。"""
        # 模拟已外部化的引用文本仍然很长的 edge case
        artifact_ref = "A" * 500
        max_chars = 200
        if len(artifact_ref) > max_chars:
            artifact_ref = artifact_ref[:max_chars] + "... [truncated]"
        assert len(artifact_ref) <= 220


# ── SUMMARY_PREFIX 策略测试 ──────────────────────────────────────


class TestSummaryPrefixStrategy:
    """SUMMARY_PREFIX 提取式摘要前缀策略。"""

    def test_summary_prefix_creates_summary_message(self) -> None:
        """被裁掉的消息生成摘要 system 消息。"""
        msgs = [
            _make_msg(MessageRole.USER, "question 1 about topology", tokens=50),
            _make_msg(MessageRole.ASSISTANT, "answer about graph theory", tokens=50),
            _make_msg(MessageRole.USER, "question 2 about algebra", tokens=50),
            _make_msg(MessageRole.ASSISTANT, "latest answer", tokens=10),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=30,  # 只能装最新 1 条
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 应有一条 summary system message + 保留的最新消息
        system_msgs = [m for m in result if m.role == MessageRole.SYSTEM]
        assert len(system_msgs) == 1
        assert "[Conversation Summary" in system_msgs[0].content
        assert "question 1" in system_msgs[0].content or "topology" in system_msgs[0].content

    def test_summary_prefix_no_pruned_messages(self) -> None:
        """所有消息都被保留时不产生摘要。"""
        msgs = [
            _make_msg(MessageRole.USER, "hi", tokens=5),
            _make_msg(MessageRole.ASSISTANT, "hello", tokens=5),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=1000,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 2
        system_msgs = [m for m in result if m.role == MessageRole.SYSTEM]
        assert len(system_msgs) == 0

    def test_summary_prefix_preserves_existing_system(self) -> None:
        """保留原有 system 消息 + 摘要。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "you are an agent", tokens=10),
            _make_msg(MessageRole.USER, "old question", tokens=50),
            _make_msg(MessageRole.ASSISTANT, "old answer", tokens=50),
            _make_msg(MessageRole.USER, "new question", tokens=10),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=30,
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        system_msgs = [m for m in result if m.role == MessageRole.SYSTEM]
        # 原 system + 生成的 summary
        assert len(system_msgs) >= 1
        non_system = [m for m in result if m.role != MessageRole.SYSTEM]
        assert len(non_system) >= 1

    def test_summary_prefix_limits_summary_items(self) -> None:
        """超过 20 条被裁消息时摘要条目被限制。"""
        msgs = [_make_msg(MessageRole.USER, f"msg {i}", tokens=5) for i in range(30)]
        # 加一条足够小的最新消息确保至少保留一条
        msgs.append(_make_msg(MessageRole.ASSISTANT, "final", tokens=5))
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=15,  # 很小的预算
        )
        result = HistoryTrimmer.trim(msgs, config)
        summary_msgs = [m for m in result if m.role == MessageRole.SYSTEM and "Conversation Summary" in (m.content or "")]
        if summary_msgs:
            # 摘要不应过长
            assert len(summary_msgs[0].content.split("\n")) <= 25

    def test_summary_prefix_empty_messages(self) -> None:
        """空消息返回空。"""
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SUMMARY_PREFIX)
        result = HistoryTrimmer.trim([], config)
        assert result == []


# ── Cache-First Prompt 测试 ──────────────────────────────────────


class TestCacheFirstPrompt:
    """Cache-First Prompt — system_prompt_prefix 分离稳定前缀。"""

    @pytest.mark.asyncio
    async def test_cache_first_produces_two_system_messages(self) -> None:
        """配置 system_prompt_prefix 后产生 2 条 system 消息。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        agent = Agent(name="test", instructions="Do the task.")
        config = RunConfig(system_prompt_prefix="You are a helpful AI assistant.")
        ctx = RunContext(agent=agent, config=config)

        msgs = await _build_system_messages(agent, ctx, config)
        assert len(msgs) == 2
        # 第一条: 稳定前缀 + cache_control 元数据
        assert msgs[0].content == "You are a helpful AI assistant."
        assert msgs[0].metadata.get("cache_control") == {"type": "ephemeral"}
        assert msgs[0].role == MessageRole.SYSTEM
        # 第二条: Agent instructions
        assert msgs[1].content == "Do the task."
        assert msgs[1].role == MessageRole.SYSTEM

    @pytest.mark.asyncio
    async def test_no_prefix_produces_single_system_message(self) -> None:
        """不配置 system_prompt_prefix 时只产生 1 条 system 消息。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        agent = Agent(name="test", instructions="Just do it.")
        config = RunConfig()
        ctx = RunContext(agent=agent, config=config)

        msgs = await _build_system_messages(agent, ctx, config)
        assert len(msgs) == 1
        assert msgs[0].content == "Just do it."

    @pytest.mark.asyncio
    async def test_prefix_only_no_instructions(self) -> None:
        """Agent 无 instructions 但有 prefix 时只产生 1 条消息。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        agent = Agent(name="test", instructions="")
        config = RunConfig(system_prompt_prefix="Global rules here.")
        ctx = RunContext(agent=agent, config=config)

        msgs = await _build_system_messages(agent, ctx, config)
        assert len(msgs) == 1
        assert msgs[0].content == "Global rules here."

    @pytest.mark.asyncio
    async def test_no_prefix_no_instructions_returns_empty(self) -> None:
        """无 prefix 无 instructions 时返回空列表。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.run_context import RunContext
        from ckyclaw_framework.runner.runner import _build_system_messages

        agent = Agent(name="test", instructions="")
        config = RunConfig()
        ctx = RunContext(agent=agent, config=config)

        msgs = await _build_system_messages(agent, ctx, config)
        assert len(msgs) == 0

    def test_system_prompt_prefix_default_none(self) -> None:
        """RunConfig 默认 system_prompt_prefix=None。"""
        from ckyclaw_framework.runner.run_config import RunConfig

        config = RunConfig()
        assert config.system_prompt_prefix is None
