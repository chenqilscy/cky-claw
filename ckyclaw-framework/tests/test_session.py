"""Session 持久化单元测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session, SessionMetadata
from ckyclaw_framework.tools.function_tool import function_tool


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
        ts = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
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
