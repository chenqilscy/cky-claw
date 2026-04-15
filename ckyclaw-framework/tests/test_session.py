"""Session 持久化单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.result import StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimmer, HistoryTrimStrategy
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import function_tool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings

# ── Mock Model Provider ─────────────────────────────────────────


class MockProvider(ModelProvider):
    """可编排的 Mock LLM 提供商。按顺序返回预设响应。"""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.call_messages: list[list[Message]] = []

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        self.call_messages.append(list(messages))
        if stream:
            return self._stream_response()
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return resp

    async def _stream_response(self) -> AsyncIterator[ModelChunk]:
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        if resp.content:
            words = resp.content.split(" ")
            for i, w in enumerate(words):
                suffix = " " if i < len(words) - 1 else ""
                yield ModelChunk(content=w + suffix)
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield ModelChunk(
                    tool_call_chunks=[
                        ToolCallChunk(index=i, id=tc.id, name=tc.name, arguments_delta=tc.arguments),
                    ],
                )
        yield ModelChunk(finish_reason="stop")


# ── Message 序列化测试 ──────────────────────────────────────────


class TestMessageSerialization:
    def test_basic_message_roundtrip(self) -> None:
        """基本消息序列化/反序列化往返。"""
        msg = Message(role=MessageRole.USER, content="Hello")
        d = msg.to_dict()
        restored = Message.from_dict(d)

        assert restored.role == MessageRole.USER
        assert restored.content == "Hello"
        assert restored.agent_name is None
        assert restored.tool_calls is None

    def test_assistant_message_with_tool_calls(self) -> None:
        """assistant 消息含 tool_calls 序列化。"""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            agent_name="bot",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "add", "arguments": '{"a":1}'}}],
            token_usage=TokenUsage(10, 5, 15),
        )
        d = msg.to_dict()
        restored = Message.from_dict(d)

        assert restored.agent_name == "bot"
        assert restored.tool_calls is not None
        assert len(restored.tool_calls) == 1
        assert restored.token_usage is not None
        assert restored.token_usage.total_tokens == 15

    def test_tool_message_roundtrip(self) -> None:
        """tool 消息序列化。"""
        msg = Message(
            role=MessageRole.TOOL,
            content="42",
            tool_call_id="call_123",
            agent_name="calc",
        )
        d = msg.to_dict()
        restored = Message.from_dict(d)

        assert restored.role == MessageRole.TOOL
        assert restored.tool_call_id == "call_123"
        assert restored.content == "42"

    def test_timestamp_preserved(self) -> None:
        """时间戳序列化精度。"""
        ts = datetime(2025, 7, 15, 12, 0, 0, tzinfo=UTC)
        msg = Message(role=MessageRole.USER, content="hi", timestamp=ts)
        d = msg.to_dict()
        restored = Message.from_dict(d)

        assert restored.timestamp == ts

    def test_metadata_preserved(self) -> None:
        """自定义 metadata 往返。"""
        msg = Message(role=MessageRole.USER, content="hi", metadata={"source": "api", "priority": 1})
        d = msg.to_dict()
        restored = Message.from_dict(d)

        assert restored.metadata == {"source": "api", "priority": 1}


# ── InMemorySessionBackend 测试 ─────────────────────────────────


class TestInMemorySessionBackend:
    @pytest.mark.asyncio
    async def test_save_and_load(self) -> None:
        """保存后能正确加载消息。"""
        backend = InMemorySessionBackend()
        msgs = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi!", agent_name="bot"),
        ]

        await backend.save("s1", msgs)
        loaded = await backend.load("s1")

        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].content == "Hello"
        assert loaded[1].content == "Hi!"

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self) -> None:
        """加载不存在的 session 返回 None。"""
        backend = InMemorySessionBackend()
        result = await backend.load("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_append_messages(self) -> None:
        """多次保存消息正确追加。"""
        backend = InMemorySessionBackend()

        await backend.save("s1", [Message(role=MessageRole.USER, content="first")])
        await backend.save("s1", [Message(role=MessageRole.ASSISTANT, content="reply", agent_name="bot")])

        loaded = await backend.load("s1")
        assert loaded is not None
        assert len(loaded) == 2

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """删除后加载返回 None。"""
        backend = InMemorySessionBackend()
        await backend.save("s1", [Message(role=MessageRole.USER, content="hi")])
        await backend.delete("s1")

        assert await backend.load("s1") is None
        assert await backend.load_metadata("s1") is None

    @pytest.mark.asyncio
    async def test_metadata_updated(self) -> None:
        """保存消息后元数据正确更新。"""
        backend = InMemorySessionBackend()
        await backend.save("s1", [
            Message(role=MessageRole.USER, content="hi"),
            Message(role=MessageRole.ASSISTANT, content="hello", agent_name="bot"),
        ])

        meta = await backend.load_metadata("s1")
        assert meta is not None
        assert meta.session_id == "s1"
        assert meta.message_count == 2
        assert meta.last_agent_name == "bot"

    @pytest.mark.asyncio
    async def test_list_sessions(self) -> None:
        """列出所有 session。"""
        backend = InMemorySessionBackend()
        await backend.save("s1", [Message(role=MessageRole.USER, content="a")])
        await backend.save("s2", [Message(role=MessageRole.USER, content="b")])

        sessions = await backend.list_sessions()
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert ids == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_save_empty_messages_noop(self) -> None:
        """保存空列表不创建 session。"""
        backend = InMemorySessionBackend()
        await backend.save("s1", [])

        assert await backend.load("s1") is None

    @pytest.mark.asyncio
    async def test_load_returns_copy(self) -> None:
        """load 返回的是副本，修改不影响内部状态。"""
        backend = InMemorySessionBackend()
        await backend.save("s1", [Message(role=MessageRole.USER, content="hi")])

        loaded = await backend.load("s1")
        assert loaded is not None
        loaded.append(Message(role=MessageRole.USER, content="extra"))

        reloaded = await backend.load("s1")
        assert reloaded is not None
        assert len(reloaded) == 1  # 内部仍然只有一条


# ── Session 类测试 ──────────────────────────────────────────────


class TestSession:
    @pytest.mark.asyncio
    async def test_get_history_without_backend(self) -> None:
        """无 backend 时返回空列表。"""
        session = Session(session_id="s1")
        history = await session.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_session_append_and_get(self) -> None:
        """通过 Session 类追加和读取。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)

        await session.append([Message(role=MessageRole.USER, content="hello")])
        history = await session.get_history()

        assert len(history) == 1
        assert history[0].content == "hello"

    @pytest.mark.asyncio
    async def test_session_clear(self) -> None:
        """清空 session 历史。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)

        await session.append([Message(role=MessageRole.USER, content="hello")])
        await session.clear()

        history = await session.get_history()
        assert history == []


# ── Runner + Session 集成测试 ───────────────────────────────────


class TestRunnerWithSession:
    @pytest.mark.asyncio
    async def test_first_turn_saves_to_session(self) -> None:
        """首次对话：消息保存到 session。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Hello!")])

        result = await Runner.run(
            agent, "Hi",
            session=session,
            config=RunConfig(model_provider=provider),
        )

        assert result.output == "Hello!"
        # Session 应保存 user + assistant 消息
        stored = await backend.load("s1")
        assert stored is not None
        assert len(stored) == 2
        assert stored[0].role == MessageRole.USER
        assert stored[0].content == "Hi"
        assert stored[1].role == MessageRole.ASSISTANT
        assert stored[1].content == "Hello!"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self) -> None:
        """多轮对话：第二轮自动加载历史。"""
        backend = InMemorySessionBackend()
        agent = Agent(name="bot")

        # 第一轮
        provider1 = MockProvider([ModelResponse(content="First reply")])
        session1 = Session(session_id="s1", backend=backend)
        await Runner.run(agent, "Turn 1", session=session1, config=RunConfig(model_provider=provider1))

        # 第二轮 —— 新 provider 能看到历史消息
        provider2 = MockProvider([ModelResponse(content="Second reply")])
        session2 = Session(session_id="s1", backend=backend)
        result = await Runner.run(agent, "Turn 2", session=session2, config=RunConfig(model_provider=provider2))

        assert result.output == "Second reply"

        # 验证 LLM 收到的消息包含历史
        # provider2.call_messages[0] 应包含：history(user+assistant) + new_user + system(if any)
        llm_messages = provider2.call_messages[0]
        # 过滤掉 system message
        non_system = [m for m in llm_messages if m.role != MessageRole.SYSTEM]
        assert len(non_system) == 3  # history_user + history_assistant + new_user
        assert non_system[0].content == "Turn 1"
        assert non_system[1].content == "First reply"
        assert non_system[2].content == "Turn 2"

        # Session 总共应有 4 条消息
        stored = await backend.load("s1")
        assert stored is not None
        assert len(stored) == 4

    @pytest.mark.asyncio
    async def test_session_with_tool_calls(self) -> None:
        """含工具调用的对话也正确保存到 session。"""
        @function_tool()
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot", tools=[greet])

        provider = MockProvider([
            ModelResponse(tool_calls=[ToolCall(id="c1", name="greet", arguments='{"name": "Alice"}')]),
            ModelResponse(content="I greeted Alice for you."),
        ])

        result = await Runner.run(
            agent, "Greet Alice",
            session=session,
            config=RunConfig(model_provider=provider),
        )

        assert result.output == "I greeted Alice for you."

        # 应保存: user + assistant(tool_call) + tool(result) + assistant(final)
        stored = await backend.load("s1")
        assert stored is not None
        assert len(stored) == 4
        assert stored[2].role == MessageRole.TOOL
        assert "Hello, Alice!" in stored[2].content

    @pytest.mark.asyncio
    async def test_no_session_backward_compatible(self) -> None:
        """不传 session 时行为与之前完全一致。"""
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="OK")])

        result = await Runner.run(agent, "test", config=RunConfig(model_provider=provider))
        assert result.output == "OK"

    @pytest.mark.asyncio
    async def test_streamed_with_session(self) -> None:
        """流式模式也正确保存到 session。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Stream reply")])

        events = []
        async for event in Runner.run_streamed(
            agent, "Hi",
            session=session,
            config=RunConfig(model_provider=provider),
        ):
            events.append(event)

        # 确认 RUN_COMPLETE 事件
        complete = [e for e in events if e.type == StreamEventType.RUN_COMPLETE]
        assert len(complete) == 1
        assert complete[0].data.output == "Stream reply"

        # Session 应保存消息
        stored = await backend.load("s1")
        assert stored is not None
        assert len(stored) == 2


# ── HistoryTrimmer 单元测试 ─────────────────────────────────────


def _make_msgs(n: int, *, prefix: str = "msg", with_system: bool = False) -> list[Message]:
    """生成 n 条 user/assistant 交替消息。可在最前面插入 system 消息。"""
    msgs: list[Message] = []
    if with_system:
        msgs.append(Message(role=MessageRole.SYSTEM, content="System prompt"))
    for i in range(n):
        role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
        msgs.append(Message(role=role, content=f"{prefix}-{i}"))
    return msgs


class TestHistoryTrimmerSlidingWindow:
    def test_no_trim_when_under_limit(self) -> None:
        """消息数未超限时不裁剪。"""
        msgs = _make_msgs(4)
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=10)
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 4

    def test_trim_to_max_messages(self) -> None:
        """超限时保留最后 N 条。"""
        msgs = _make_msgs(10)
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=4)
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 4
        assert result[0].content == "msg-6"
        assert result[-1].content == "msg-9"

    def test_system_messages_preserved(self) -> None:
        """keep_system_messages=True 时 system 消息占用配额但始终保留。"""
        msgs = _make_msgs(10, with_system=True)  # 1 system + 10 content = 11 total
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            max_history_messages=4,
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # system(1) + last 3 non-system = 4
        assert len(result) == 4
        assert result[0].role == MessageRole.SYSTEM
        assert result[1].content == "msg-7"

    def test_system_messages_not_preserved(self) -> None:
        """keep_system_messages=False 时 system 消息也参与裁剪。"""
        msgs = _make_msgs(10, with_system=True)
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            max_history_messages=3,
            keep_system_messages=False,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 3
        assert all(m.role != MessageRole.SYSTEM for m in result)

    def test_empty_messages(self) -> None:
        """空列表返回空列表。"""
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=5)
        assert HistoryTrimmer.trim([], config) == []

    def test_max_one_message(self) -> None:
        """max_history_messages=1 只保留最后一条。"""
        msgs = _make_msgs(5)
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=1)
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 1
        assert result[0].content == "msg-4"


class TestHistoryTrimmerTokenBudget:
    def test_no_trim_when_under_budget(self) -> None:
        """Token 未超预算时不裁剪。"""
        msgs = [Message(role=MessageRole.USER, content="hi")]
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.TOKEN_BUDGET, max_history_tokens=1000)
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 1

    def test_trim_oldest_first(self) -> None:
        """超预算时从最老的消息开始丢弃。"""
        # 每条消息约 content_len/3 tokens
        msgs = [
            Message(role=MessageRole.USER, content="a" * 300),     # ~100 tokens
            Message(role=MessageRole.ASSISTANT, content="b" * 300),  # ~100 tokens
            Message(role=MessageRole.USER, content="c" * 300),     # ~100 tokens
            Message(role=MessageRole.ASSISTANT, content="d" * 300),  # ~100 tokens
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=250,  # 只能放 ~2.5 条
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 从最新向前累加：d(100) + c(100) = 200 ≤ 250, + b(100) = 300 > 250
        assert len(result) == 2
        assert result[0].content == "c" * 300
        assert result[1].content == "d" * 300

    def test_system_messages_preserved_in_token_budget(self) -> None:
        """TOKEN_BUDGET 策略也保留 system 消息。"""
        msgs = [
            Message(role=MessageRole.SYSTEM, content="System prompt"),
            Message(role=MessageRole.USER, content="a" * 300),
            Message(role=MessageRole.ASSISTANT, content="b" * 300),
            Message(role=MessageRole.USER, content="c" * 300),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=150,
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert result[0].role == MessageRole.SYSTEM
        assert result[-1].content == "c" * 300

    def test_token_budget_with_token_usage(self) -> None:
        """有 token_usage 时优先使用精确值。"""
        msgs = [
            Message(role=MessageRole.USER, content="short", token_usage=TokenUsage(50, 0, 50)),
            Message(role=MessageRole.ASSISTANT, content="medium", token_usage=TokenUsage(0, 100, 100)),
            Message(role=MessageRole.USER, content="long", token_usage=TokenUsage(80, 0, 80)),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=190,  # long(80) + medium(100) = 180 ≤ 190, + short(50) = 230 > 190
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 2
        assert result[0].content == "medium"
        assert result[1].content == "long"

    def test_max_messages_hard_cap(self) -> None:
        """TOKEN_BUDGET 策略中 max_history_messages 作为硬上限。"""
        # 所有消息都很短，Token 不会超预算
        msgs = _make_msgs(20)
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=999999,
            max_history_messages=5,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 5

    def test_empty_messages_token_budget(self) -> None:
        """空列表 TOKEN_BUDGET 返回空。"""
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.TOKEN_BUDGET, max_history_tokens=100)
        assert HistoryTrimmer.trim([], config) == []


class TestHistoryTrimmerSummaryPrefix:
    def test_summary_prefix_produces_summary_and_recent(self) -> None:
        """SUMMARY_PREFIX 将被裁掉的消息浓缩为摘要 + 保留最近消息。"""
        msgs = [
            Message(role=MessageRole.USER, content="a" * 300),
            Message(role=MessageRole.ASSISTANT, content="b" * 300),
            Message(role=MessageRole.USER, content="c" * 300),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=150,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 应有摘要 system msg + 最近的消息
        assert len(result) >= 1
        # 最后一条应是最新的用户消息
        non_system = [m for m in result if m.role != MessageRole.SYSTEM]
        assert non_system[-1].content == "c" * 300
        # 有摘要 system 消息
        summary_msgs = [m for m in result if m.role == MessageRole.SYSTEM]
        assert len(summary_msgs) >= 1
        assert "Conversation Summary" in summary_msgs[0].content


# ── Session.trim() 测试 ─────────────────────────────────────────


class TestSessionTrim:
    @pytest.mark.asyncio
    async def test_trim_returns_trimmed_history(self) -> None:
        """Session.trim() 返回裁剪后的历史列表。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)

        # 保存 10 条消息
        for i in range(10):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            await session.append([Message(role=role, content=f"m-{i}")])

        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=3)
        trimmed = await session.trim(config)

        assert len(trimmed) == 3
        assert trimmed[0].content == "m-7"
        assert trimmed[-1].content == "m-9"

    @pytest.mark.asyncio
    async def test_trim_does_not_modify_backend(self) -> None:
        """Session.trim() 不修改后端存储中的数据。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)

        for i in range(6):
            await session.append([Message(role=MessageRole.USER, content=f"m-{i}")])

        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=2)
        await session.trim(config)

        # 后端数据不变
        full = await backend.load("s1")
        assert full is not None
        assert len(full) == 6

    @pytest.mark.asyncio
    async def test_trim_empty_history(self) -> None:
        """空历史 trim 返回空列表。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="s1", backend=backend)

        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=5)
        trimmed = await session.trim(config)
        assert trimmed == []

    @pytest.mark.asyncio
    async def test_trim_without_backend(self) -> None:
        """无 backend 的 Session.trim() 返回空列表。"""
        session = Session(session_id="s1")
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=5)
        trimmed = await session.trim(config)
        assert trimmed == []


# ── Runner + Session 自动裁剪集成测试 ───────────────────────────


class TestRunnerWithAutoTrim:
    @pytest.mark.asyncio
    async def test_auto_trim_sliding_window(self) -> None:
        """Runner 在加载 Session 历史后自动裁剪（SLIDING_WINDOW）。"""
        backend = InMemorySessionBackend()

        # 预填充 20 条历史消息
        for i in range(20):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            await backend.save("s1", [Message(role=role, content=f"old-{i}")])

        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Ok")])

        result = await Runner.run(
            agent, "new question",
            session=session,
            config=RunConfig(
                model_provider=provider,
                max_history_messages=4,
                history_trim_strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            ),
        )

        assert result.output == "Ok"

        # 验证 LLM 收到的消息：system(可能) + trimmed_history(4) + new_user(1)
        llm_messages = provider.call_messages[0]
        non_system = [m for m in llm_messages if m.role != MessageRole.SYSTEM]
        assert len(non_system) == 5  # 4 history + 1 new
        # 最老的裁剪后消息是 old-16
        assert non_system[0].content == "old-16"

    @pytest.mark.asyncio
    async def test_auto_trim_token_budget(self) -> None:
        """Runner 在加载 Session 历史后自动裁剪（TOKEN_BUDGET）。"""
        backend = InMemorySessionBackend()

        # 保存几条大消息
        await backend.save("s1", [
            Message(role=MessageRole.USER, content="a" * 300),      # ~100 tokens
            Message(role=MessageRole.ASSISTANT, content="b" * 300),  # ~100 tokens
            Message(role=MessageRole.USER, content="c" * 300),      # ~100 tokens
            Message(role=MessageRole.ASSISTANT, content="d" * 300),  # ~100 tokens
        ])

        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Ok")])

        result = await Runner.run(
            agent, "question",
            session=session,
            config=RunConfig(
                model_provider=provider,
                max_history_tokens=250,
                history_trim_strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            ),
        )

        assert result.output == "Ok"

        # 验证裁剪后 LLM 收到的历史消息减少了
        llm_messages = provider.call_messages[0]
        non_system = [m for m in llm_messages if m.role != MessageRole.SYSTEM]
        # c(100) + d(100) = 200 ≤ 250，a+b 被裁掉
        assert len(non_system) == 3  # 2 history + 1 new
        assert non_system[0].content == "c" * 300

    @pytest.mark.asyncio
    async def test_no_trim_without_config(self) -> None:
        """不设置 max_history_tokens/messages 时不裁剪。"""
        backend = InMemorySessionBackend()

        for i in range(10):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            await backend.save("s1", [Message(role=role, content=f"old-{i}")])

        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Ok")])

        await Runner.run(
            agent, "new",
            session=session,
            config=RunConfig(model_provider=provider),
        )

        # 验证 LLM 收到了全部历史
        llm_messages = provider.call_messages[0]
        non_system = [m for m in llm_messages if m.role != MessageRole.SYSTEM]
        assert len(non_system) == 11  # 10 history + 1 new

    @pytest.mark.asyncio
    async def test_auto_trim_streamed(self) -> None:
        """流式模式也触发自动裁剪。"""
        backend = InMemorySessionBackend()

        for i in range(10):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            await backend.save("s1", [Message(role=role, content=f"old-{i}")])

        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Stream Ok")])

        events = []
        async for event in Runner.run_streamed(
            agent, "new",
            session=session,
            config=RunConfig(
                model_provider=provider,
                max_history_messages=3,
                history_trim_strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            ),
        ):
            events.append(event)

        complete = [e for e in events if e.type == StreamEventType.RUN_COMPLETE]
        assert len(complete) == 1
        assert complete[0].data.output == "Stream Ok"

        # 验证 LLM 收到裁剪后的历史
        llm_messages = provider.call_messages[0]
        non_system = [m for m in llm_messages if m.role != MessageRole.SYSTEM]
        assert len(non_system) == 4  # 3 history + 1 new

    @pytest.mark.asyncio
    async def test_session_still_saves_all_new_messages(self) -> None:
        """自动裁剪只影响 LLM 上下文，新消息仍全部保存到 Session。"""
        backend = InMemorySessionBackend()

        # 预填充 5 条
        for i in range(5):
            await backend.save("s1", [Message(role=MessageRole.USER, content=f"old-{i}")])

        session = Session(session_id="s1", backend=backend)
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="Reply")])

        await Runner.run(
            agent, "new question",
            session=session,
            config=RunConfig(
                model_provider=provider,
                max_history_messages=2,
                history_trim_strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            ),
        )

        # Session 后端应保存全部历史（5 old + 1 new_user + 1 assistant）= 7
        stored = await backend.load("s1")
        assert stored is not None
        assert len(stored) == 7
