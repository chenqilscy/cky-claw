"""Checkpoint 机制单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ckyclaw_framework.checkpoint import (
    Checkpoint,
    InMemoryCheckpointBackend,
)

# ═══════════════════════════════════════════════════════════════════
# Checkpoint 数据类测试
# ═══════════════════════════════════════════════════════════════════


class TestCheckpoint:
    """Checkpoint 数据类。"""

    def test_defaults(self) -> None:
        """验证默认字段值。"""
        cp = Checkpoint()
        assert cp.checkpoint_id
        assert cp.run_id == ""
        assert cp.turn_count == 0
        assert cp.current_agent_name == ""
        assert cp.messages == []
        assert cp.token_usage == {}
        assert cp.context == {}
        assert isinstance(cp.created_at, datetime)

    def test_custom_fields(self) -> None:
        """自定义字段赋值。"""
        cp = Checkpoint(
            checkpoint_id="cp-1",
            run_id="run-1",
            turn_count=3,
            current_agent_name="agent-a",
            messages=[{"role": "user", "content": "hello"}],
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            context={"key": "value"},
        )
        assert cp.checkpoint_id == "cp-1"
        assert cp.run_id == "run-1"
        assert cp.turn_count == 3
        assert cp.current_agent_name == "agent-a"
        assert len(cp.messages) == 1
        assert cp.token_usage["total_tokens"] == 150
        assert cp.context["key"] == "value"

    def test_to_dict(self) -> None:
        """序列化为字典。"""
        cp = Checkpoint(
            checkpoint_id="cp-1",
            run_id="run-1",
            turn_count=2,
            current_agent_name="agent-b",
        )
        d = cp.to_dict()
        assert d["checkpoint_id"] == "cp-1"
        assert d["run_id"] == "run-1"
        assert d["turn_count"] == 2
        assert isinstance(d["created_at"], str)

    def test_from_dict(self) -> None:
        """从字典反序列化。"""
        cp = Checkpoint(
            checkpoint_id="cp-1",
            run_id="run-1",
            turn_count=5,
            current_agent_name="agent-c",
        )
        d = cp.to_dict()
        restored = Checkpoint.from_dict(d)
        assert restored.checkpoint_id == "cp-1"
        assert restored.run_id == "run-1"
        assert restored.turn_count == 5
        assert restored.current_agent_name == "agent-c"
        assert isinstance(restored.created_at, datetime)

    def test_from_dict_datetime_object(self) -> None:
        """from_dict 接受 datetime 对象。"""
        now = datetime.now(UTC)
        d = {
            "checkpoint_id": "cp-2",
            "run_id": "run-2",
            "turn_count": 1,
            "current_agent_name": "x",
            "messages": [],
            "token_usage": {},
            "context": {},
            "created_at": now,
        }
        restored = Checkpoint.from_dict(d)
        assert restored.created_at == now


# ═══════════════════════════════════════════════════════════════════
# InMemoryCheckpointBackend 测试
# ═══════════════════════════════════════════════════════════════════


class TestInMemoryCheckpointBackend:
    """InMemoryCheckpointBackend 存储测试。"""

    @pytest.fixture()
    def backend(self) -> InMemoryCheckpointBackend:
        return InMemoryCheckpointBackend()

    @pytest.mark.asyncio
    async def test_save_and_load_latest(self, backend: InMemoryCheckpointBackend) -> None:
        """保存后加载最新 checkpoint。"""
        cp1 = Checkpoint(run_id="r1", turn_count=1, current_agent_name="a")
        cp2 = Checkpoint(run_id="r1", turn_count=3, current_agent_name="b")
        cp3 = Checkpoint(run_id="r1", turn_count=2, current_agent_name="c")
        await backend.save(cp1)
        await backend.save(cp2)
        await backend.save(cp3)

        latest = await backend.load_latest("r1")
        assert latest is not None
        assert latest.turn_count == 3
        assert latest.current_agent_name == "b"

    @pytest.mark.asyncio
    async def test_load_latest_nonexistent(self, backend: InMemoryCheckpointBackend) -> None:
        """不存在的 run_id 返回 None。"""
        result = await backend.load_latest("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, backend: InMemoryCheckpointBackend) -> None:
        """列出所有 checkpoint 按 turn_count 升序。"""
        cp1 = Checkpoint(run_id="r1", turn_count=3)
        cp2 = Checkpoint(run_id="r1", turn_count=1)
        cp3 = Checkpoint(run_id="r1", turn_count=2)
        await backend.save(cp1)
        await backend.save(cp2)
        await backend.save(cp3)

        result = await backend.list_checkpoints("r1")
        assert len(result) == 3
        assert [c.turn_count for c in result] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_list_empty(self, backend: InMemoryCheckpointBackend) -> None:
        """空列表。"""
        result = await backend.list_checkpoints("nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_delete(self, backend: InMemoryCheckpointBackend) -> None:
        """删除所有 checkpoint。"""
        await backend.save(Checkpoint(run_id="r1", turn_count=1))
        await backend.save(Checkpoint(run_id="r1", turn_count=2))
        await backend.delete("r1")

        result = await backend.list_checkpoints("r1")
        assert result == []
        latest = await backend.load_latest("r1")
        assert latest is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend: InMemoryCheckpointBackend) -> None:
        """删除不存在的 run_id 不报错。"""
        await backend.delete("nonexistent")  # no error

    @pytest.mark.asyncio
    async def test_isolation_between_run_ids(self, backend: InMemoryCheckpointBackend) -> None:
        """不同 run_id 隔离。"""
        await backend.save(Checkpoint(run_id="r1", turn_count=1))
        await backend.save(Checkpoint(run_id="r2", turn_count=5))

        r1 = await backend.load_latest("r1")
        r2 = await backend.load_latest("r2")
        assert r1 is not None and r1.turn_count == 1
        assert r2 is not None and r2.turn_count == 5


# ═══════════════════════════════════════════════════════════════════
# Runner 集成测试 — checkpoint 保存与恢复
# ═══════════════════════════════════════════════════════════════════


class TestRunnerCheckpointIntegration:
    """Runner 与 checkpoint 集成测试（使用 mock LLM）。"""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_during_run(self) -> None:
        """Runner 执行过程中保存 checkpoint。"""
        from unittest.mock import AsyncMock, MagicMock

        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import TokenUsage
        from ckyclaw_framework.model.provider import ModelResponse, ToolCall
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.runner import Runner
        from ckyclaw_framework.tools.function_tool import function_tool

        # 构造一个会执行 1 轮工具调用再返回的 mock provider
        call_count = 0

        async def mock_chat(**kwargs: object) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ModelResponse(
                    content="",
                    tool_calls=[ToolCall(id="tc1", name="greet", arguments='{"name":"world"}')],
                    token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                )
            return ModelResponse(
                content="Hello world!",
                tool_calls=[],
                token_usage=TokenUsage(prompt_tokens=8, completion_tokens=3, total_tokens=11),
            )

        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=mock_chat)

        @function_tool()
        async def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        agent = Agent(
            name="test-agent",
            instructions="You are a test agent.",
            tools=[greet],
        )

        backend = InMemoryCheckpointBackend()
        config = RunConfig(
            model="mock",
            model_provider=provider,
            tracing_enabled=False,
            checkpoint_backend=backend,
            checkpoint_interval=1,
        )

        result = await Runner.run(agent, "say hi", config=config, max_turns=5)
        assert result.output == "Hello world!"
        assert result.run_id is not None

        # 应有 1 个 checkpoint（工具调用那一轮）
        checkpoints = await backend.list_checkpoints(result.run_id)
        assert len(checkpoints) == 1
        assert checkpoints[0].turn_count == 1
        assert checkpoints[0].current_agent_name == "test-agent"

    @pytest.mark.asyncio
    async def test_checkpoint_interval(self) -> None:
        """checkpoint_interval=2 时每 2 轮保存一次。"""
        from unittest.mock import AsyncMock, MagicMock

        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import TokenUsage
        from ckyclaw_framework.model.provider import ModelResponse, ToolCall
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.runner import Runner
        from ckyclaw_framework.tools.function_tool import function_tool as ft_decorator

        call_count = 0

        async def mock_chat(**kwargs: object) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return ModelResponse(
                    content="",
                    tool_calls=[ToolCall(id=f"tc{call_count}", name="inc", arguments="{}")],
                    token_usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
                )
            return ModelResponse(
                content="done",
                tool_calls=[],
                token_usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
            )

        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=mock_chat)

        @ft_decorator()
        async def inc() -> str:
            """Increment."""
            return "ok"

        agent = Agent(
            name="counter",
            instructions="Count.",
            tools=[inc],
        )

        backend = InMemoryCheckpointBackend()
        config = RunConfig(
            model="mock",
            model_provider=provider,
            tracing_enabled=False,
            checkpoint_backend=backend,
            checkpoint_interval=2,
        )

        result = await Runner.run(agent, "count", config=config, max_turns=10)
        assert result.output == "done"

        # 3 轮工具调用，interval=2 → turn 2 保存（turn 1 跳过、turn 3 跳过因 3%2≠0）
        checkpoints = await backend.list_checkpoints(result.run_id)
        assert len(checkpoints) == 1
        assert checkpoints[0].turn_count == 2

    @pytest.mark.asyncio
    async def test_run_id_in_result(self) -> None:
        """RunResult 包含 run_id。"""
        from unittest.mock import AsyncMock, MagicMock

        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import TokenUsage
        from ckyclaw_framework.model.provider import ModelResponse
        from ckyclaw_framework.runner.run_config import RunConfig
        from ckyclaw_framework.runner.runner import Runner

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=ModelResponse(
            content="hi",
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        ))

        agent = Agent(name="a", instructions="test")
        config = RunConfig(model="mock", model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "hello", config=config)
        assert result.run_id is not None
        assert isinstance(result.run_id, str)
        assert len(result.run_id) > 0

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self) -> None:
        """从 checkpoint 恢复执行。"""
        from ckyclaw_framework.model.message import Message, MessageRole

        backend = InMemoryCheckpointBackend()
        run_id = "test-resume-run"

        # 手动创建一个 checkpoint
        cp = Checkpoint(
            run_id=run_id,
            turn_count=2,
            current_agent_name="test-agent",
            messages=[
                Message(role=MessageRole.USER, content="start"),
                Message(role=MessageRole.ASSISTANT, content="step 1"),
                Message(role=MessageRole.USER, content="continue"),
                Message(role=MessageRole.ASSISTANT, content="step 2"),
            ],
            token_usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        )
        await backend.save(cp)

        # 验证 checkpoint 可被加载
        loaded = await backend.load_latest(run_id)
        assert loaded is not None
        assert loaded.turn_count == 2
        assert len(loaded.messages) == 4


# ═══════════════════════════════════════════════════════════════════
# _find_agent_by_name 测试
# ═══════════════════════════════════════════════════════════════════


class TestFindAgentByName:
    """_find_agent_by_name 辅助函数测试。"""

    def test_find_root(self) -> None:
        """查找根 Agent。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.runner import _find_agent_by_name

        root = Agent(name="root", instructions="test")
        assert _find_agent_by_name(root, "root") is root

    def test_find_handoff_target(self) -> None:
        """查找 handoff 目标 Agent。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.handoff.handoff import Handoff
        from ckyclaw_framework.runner.runner import _find_agent_by_name

        child = Agent(name="child", instructions="test")
        root = Agent(name="root", instructions="test", handoffs=[Handoff(agent=child)])
        assert _find_agent_by_name(root, "child") is child

    def test_find_nested(self) -> None:
        """递归查找嵌套 handoff。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.handoff.handoff import Handoff
        from ckyclaw_framework.runner.runner import _find_agent_by_name

        grandchild = Agent(name="gc", instructions="test")
        child = Agent(name="child", instructions="test", handoffs=[Handoff(agent=grandchild)])
        root = Agent(name="root", instructions="test", handoffs=[Handoff(agent=child)])
        assert _find_agent_by_name(root, "gc") is grandchild

    def test_not_found(self) -> None:
        """未找到返回 None。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.runner import _find_agent_by_name

        root = Agent(name="root", instructions="test")
        assert _find_agent_by_name(root, "missing") is None
