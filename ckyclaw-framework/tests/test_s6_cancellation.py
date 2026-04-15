"""S6 取消与检查点 — Framework 测试。

覆盖：
- CancellationToken 基础、父子级联、回调
- Runner 取消集成
- TeamRunner 取消级联
- RunConfig cancel_token 字段
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.runner.cancellation import CancellationToken
from ckyclaw_framework.runner.run_config import RunConfig

# ===========================================================================
# CancellationToken 基础
# ===========================================================================


class TestCancellationTokenBasics:
    """CancellationToken 基础功能。"""

    def test_initial_state(self) -> None:
        """初始未取消。"""
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel(self) -> None:
        """取消后状态变更。"""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_double_cancel_idempotent(self) -> None:
        """重复取消幂等。"""
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled

    def test_check_not_cancelled(self) -> None:
        """未取消时 check() 不抛出。"""
        token = CancellationToken()
        token.check()  # 不应抛出

    def test_check_cancelled_raises(self) -> None:
        """已取消时 check() 抛出 CancelledError。"""
        token = CancellationToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.check()

    @pytest.mark.anyio()
    async def test_wait(self) -> None:
        """wait() 在取消后立即返回。"""
        token = CancellationToken()

        async def _cancel_after_delay() -> None:
            await asyncio.sleep(0.01)
            token.cancel()

        asyncio.create_task(_cancel_after_delay())
        await asyncio.wait_for(token.wait(), timeout=1.0)
        assert token.is_cancelled


# ===========================================================================
# CancellationToken 父子级联
# ===========================================================================


class TestCancellationTokenCascade:
    """父子级联取消。"""

    def test_parent_cancel_cascades_to_child(self) -> None:
        """取消父级，子级同步取消。"""
        parent = CancellationToken()
        child = parent.create_child()

        parent.cancel()
        assert child.is_cancelled

    def test_child_cancel_does_not_affect_parent(self) -> None:
        """取消子级不影响父级。"""
        parent = CancellationToken()
        child = parent.create_child()

        child.cancel()
        assert child.is_cancelled
        assert not parent.is_cancelled

    def test_multi_level_cascade(self) -> None:
        """三级级联取消。"""
        root = CancellationToken()
        child = root.create_child()
        grandchild = child.create_child()

        root.cancel()
        assert child.is_cancelled
        assert grandchild.is_cancelled

    def test_sibling_independence(self) -> None:
        """同级兄弟不相互影响。"""
        parent = CancellationToken()
        child1 = parent.create_child()
        child2 = parent.create_child()

        child1.cancel()
        assert not child2.is_cancelled
        assert not parent.is_cancelled

    def test_child_of_cancelled_parent_starts_cancelled(self) -> None:
        """已取消的父级创建的子级直接处于取消状态。"""
        parent = CancellationToken()
        parent.cancel()

        child = parent.create_child()
        assert child.is_cancelled


# ===========================================================================
# CancellationToken 回调
# ===========================================================================


class TestCancellationTokenCallbacks:
    """取消回调。"""

    def test_on_cancel_fires(self) -> None:
        """回调在取消时触发。"""
        token = CancellationToken()
        called = []
        token.on_cancel(lambda: called.append(1))

        token.cancel()
        assert called == [1]

    def test_on_cancel_already_cancelled(self) -> None:
        """已取消时注册回调立即触发。"""
        token = CancellationToken()
        token.cancel()

        called = []
        token.on_cancel(lambda: called.append(1))
        assert called == [1]

    def test_multiple_callbacks(self) -> None:
        """多个回调按注册顺序触发。"""
        token = CancellationToken()
        order: list[int] = []
        token.on_cancel(lambda: order.append(1))
        token.on_cancel(lambda: order.append(2))

        token.cancel()
        assert order == [1, 2]


# ===========================================================================
# RunConfig cancel_token 字段
# ===========================================================================


class TestRunConfigCancelToken:
    """RunConfig 的 cancel_token 字段。"""

    def test_default_none(self) -> None:
        """默认无取消令牌。"""
        config = RunConfig()
        assert config.cancel_token is None

    def test_set_cancel_token(self) -> None:
        """设置取消令牌。"""
        token = CancellationToken()
        config = RunConfig(cancel_token=token)
        assert config.cancel_token is token

    def test_replace_cancel_token(self) -> None:
        """dataclasses.replace 可替换令牌。"""
        from dataclasses import replace

        token1 = CancellationToken()
        token2 = CancellationToken()
        config = RunConfig(cancel_token=token1)
        config2 = replace(config, cancel_token=token2)
        assert config2.cancel_token is token2
        assert config.cancel_token is token1  # 原始不变


# ===========================================================================
# Runner 取消集成
# ===========================================================================


class TestRunnerCancellation:
    """Runner 中的 CancellationToken 集成。"""

    @pytest.mark.anyio()
    async def test_runner_run_respects_cancel_token(self) -> None:
        """Runner.run() 在取消令牌触发时抛出 CancelledError。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.runner import Runner

        agent = Agent(name="test", instructions="test")
        token = CancellationToken()
        token.cancel()  # 预先取消

        config = RunConfig(cancel_token=token)

        with pytest.raises(asyncio.CancelledError):
            await Runner.run(agent, "hello", config=config)

    @pytest.mark.anyio()
    async def test_runner_run_without_cancel_token(self) -> None:
        """无取消令牌时 Runner 正常进入执行（mock provider）。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.model.message import TokenUsage
        from ckyclaw_framework.model.provider import ModelProvider, ModelResponse
        from ckyclaw_framework.runner.runner import Runner

        agent = Agent(name="test", instructions="test")

        response = ModelResponse(
            content="ok",
            tool_calls=[],
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        mock_provider = AsyncMock(spec=ModelProvider)
        mock_provider.chat = AsyncMock(return_value=response)

        config = RunConfig(model="test-model", model_provider=mock_provider)
        result = await Runner.run(agent, "hello", config=config)
        assert result.output == "ok"


# ===========================================================================
# TeamRunner 取消级联
# ===========================================================================


class TestTeamRunnerCancellation:
    """TeamRunner 取消级联功能。"""

    @pytest.mark.anyio()
    async def test_sequential_team_respects_cancel(self) -> None:
        """SEQUENTIAL 模式在取消时中断。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.team.protocol import TeamProtocol
        from ckyclaw_framework.team.team import Team
        from ckyclaw_framework.team.team_runner import TeamRunner

        agent1 = Agent(name="a1", instructions="test")
        agent2 = Agent(name="a2", instructions="test")
        team = Team(name="test-team", members=[agent1, agent2], protocol=TeamProtocol.SEQUENTIAL)

        token = CancellationToken()
        token.cancel()
        config = RunConfig(cancel_token=token)

        with pytest.raises(asyncio.CancelledError):
            await TeamRunner.run(team, "hello", config=config)

    @pytest.mark.anyio()
    async def test_parallel_team_respects_cancel(self) -> None:
        """PARALLEL 模式在取消时中断。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.team.protocol import TeamProtocol
        from ckyclaw_framework.team.team import Team
        from ckyclaw_framework.team.team_runner import TeamRunner

        agent1 = Agent(name="a1", instructions="test")
        agent2 = Agent(name="a2", instructions="test")
        team = Team(name="test-team", members=[agent1, agent2], protocol=TeamProtocol.PARALLEL)

        token = CancellationToken()
        token.cancel()
        config = RunConfig(cancel_token=token)

        with pytest.raises(asyncio.CancelledError):
            await TeamRunner.run(team, "hello", config=config)

    @pytest.mark.anyio()
    async def test_coordinator_team_respects_cancel(self) -> None:
        """COORDINATOR 模式在取消时中断。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.team.protocol import TeamProtocol
        from ckyclaw_framework.team.team import Team
        from ckyclaw_framework.team.team_runner import TeamRunner

        coordinator = Agent(name="coord", instructions="coordinate")
        member = Agent(name="m1", instructions="test")
        team = Team(
            name="test-team",
            members=[member],
            coordinator=coordinator,
            protocol=TeamProtocol.COORDINATOR,
        )

        token = CancellationToken()
        token.cancel()
        config = RunConfig(cancel_token=token)

        with pytest.raises(asyncio.CancelledError):
            await TeamRunner.run(team, "hello", config=config)

    @pytest.mark.anyio()
    async def test_sequential_child_tokens_created(self) -> None:
        """SEQUENTIAL 模式为每个成员创建子 Token。"""
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.runner.runner import Runner
        from ckyclaw_framework.team.protocol import TeamProtocol
        from ckyclaw_framework.team.team import Team
        from ckyclaw_framework.team.team_runner import TeamRunner

        agent = Agent(name="a1", instructions="test")
        team = Team(name="t", members=[agent], protocol=TeamProtocol.SEQUENTIAL)

        parent_token = CancellationToken()
        config = RunConfig(cancel_token=parent_token)

        # Mock Runner.run 来捕获传入的 config
        captured_configs: list[RunConfig] = []

        async def mock_run(agent: Any, input: str, **kwargs: Any) -> MagicMock:
            captured_configs.append(kwargs.get("config"))
            result = MagicMock()
            result.output = "done"
            result.token_usage = None
            result.last_agent_name = "a1"
            return result

        with patch.object(Runner, "run", side_effect=mock_run):
            await TeamRunner.run(team, "hello", config=config)

        assert len(captured_configs) == 1
        child_token = captured_configs[0].cancel_token
        # 子 token 不等于父 token
        assert child_token is not parent_token
        # 取消父 token 应级联到子 token
        parent_token.cancel()
        assert child_token.is_cancelled


# ===========================================================================
# CancellationToken 导出
# ===========================================================================


class TestCancellationExports:
    """公共 API 导出。"""

    def test_export_from_runner_package(self) -> None:
        """CancellationToken 可从 runner 包导入。"""
        from ckyclaw_framework.runner import CancellationToken as CT

        assert CT is CancellationToken
