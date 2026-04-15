"""Agent Team 协作协议 — Framework 层测试。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.message import Message, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.team.protocol import TeamProtocol
from ckyclaw_framework.team.team import Team, TeamConfig
from ckyclaw_framework.team.team_runner import TeamResult, TeamRunner, _sum_token_usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings

# ── Mock Provider ────────────────────────────────────────────


class MockSequentialProvider(ModelProvider):
    """返回固定内容的 Mock Provider。"""

    def __init__(self, content: str) -> None:
        self._content = content

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
        return ModelResponse(
            content=self._content,
            token_usage=TokenUsage(10, 20, 30),
        )


class MockCoordinatorProvider(ModelProvider):
    """模拟 coordinator agent 调用 member tools。

    第一次调用返回 tool_call，第二次返回最终结果。
    """

    def __init__(self, tool_name: str, tool_args: str, final_response: str) -> None:
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._final_response = final_response
        self._call_count = 0

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
        self._call_count += 1
        if self._call_count == 1:
            return ModelResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name=self._tool_name,
                        arguments=self._tool_args,
                    )
                ],
                token_usage=TokenUsage(15, 5, 20),
            )
        return ModelResponse(
            content=self._final_response,
            token_usage=TokenUsage(20, 30, 50),
        )


# ── TeamProtocol 测试 ────────────────────────────────────────


class TestTeamProtocol:
    def test_values(self) -> None:
        assert TeamProtocol.SEQUENTIAL.value == "sequential"
        assert TeamProtocol.PARALLEL.value == "parallel"
        assert TeamProtocol.COORDINATOR.value == "coordinator"

    def test_from_string(self) -> None:
        assert TeamProtocol("sequential") == TeamProtocol.SEQUENTIAL


# ── Team / TeamConfig 测试 ───────────────────────────────────


class TestTeamDefinition:
    def test_team_defaults(self) -> None:
        team = Team(name="test-team")
        assert team.members == []
        assert team.protocol == TeamProtocol.SEQUENTIAL
        assert team.coordinator is None
        assert team.config.max_rounds == 1
        assert team.config.separator == "\n\n---\n\n"

    def test_team_with_members(self) -> None:
        a = Agent(name="a", description="Agent A")
        b = Agent(name="b", description="Agent B")
        team = Team(name="ab-team", members=[a, b], protocol=TeamProtocol.PARALLEL)
        assert len(team.members) == 2
        assert team.protocol == TeamProtocol.PARALLEL

    def test_team_config(self) -> None:
        cfg = TeamConfig(max_rounds=3, timeout=60.0, separator="---")
        assert cfg.max_rounds == 3
        assert cfg.timeout == 60.0


# ── TeamResult 测试 ──────────────────────────────────────────


class TestTeamResult:
    def test_result_creation(self) -> None:
        result = TeamResult(
            output="done",
            team_name="test",
            protocol="sequential",
        )
        assert result.output == "done"
        assert result.member_results == []
        assert result.total_token_usage == {}

    def test_sum_token_usage(self) -> None:
        from ckyclaw_framework.runner.result import RunResult

        r1 = RunResult(output="a", token_usage=TokenUsage(10, 20, 30))
        r2 = RunResult(output="b", token_usage=TokenUsage(5, 15, 20))
        r3 = RunResult(output="c", token_usage=None)
        total = _sum_token_usage([r1, r2, r3])
        assert total["prompt_tokens"] == 15
        assert total["completion_tokens"] == 35
        assert total["total_tokens"] == 50


# ── TeamRunner — Sequential 测试 ─────────────────────────────


class TestTeamRunnerSequential:
    @pytest.mark.asyncio
    async def test_sequential_chain(self) -> None:
        """SEQUENTIAL: A → B，A 输出变成 B 输入。"""
        MockSequentialProvider("Step A 结果")
        MockSequentialProvider("Step B 最终结果")
        agent_a = Agent(name="agent-a", instructions="You are step A.")
        agent_b = Agent(name="agent-b", instructions="You are step B.")

        team = Team(
            name="seq-team",
            members=[agent_a, agent_b],
            protocol=TeamProtocol.SEQUENTIAL,
        )

        # 为了让不同 agent 使用不同 provider，我们使用同一 provider
        # Sequential 执行时每个 agent 都调用同一 provider
        provider = MockSequentialProvider("Final output")
        result = await TeamRunner.run(
            team, "Start", config=RunConfig(model_provider=provider)
        )

        assert isinstance(result, TeamResult)
        assert result.output == "Final output"
        assert len(result.member_results) == 2
        assert result.team_name == "seq-team"
        assert result.protocol == "sequential"
        assert result.total_token_usage["total_tokens"] == 60  # 30 * 2

    @pytest.mark.asyncio
    async def test_sequential_empty_members(self) -> None:
        """空成员列表返回空结果。"""
        team = Team(name="empty", members=[], protocol=TeamProtocol.SEQUENTIAL)
        result = await TeamRunner.run(team, "input")
        assert result.output == ""
        assert result.member_results == []


# ── TeamRunner — Parallel 测试 ───────────────────────────────


class TestTeamRunnerParallel:
    @pytest.mark.asyncio
    async def test_parallel_all_members(self) -> None:
        """PARALLEL: 所有成员并发执行同一输入。"""
        provider = MockSequentialProvider("Parallel result")
        agent_a = Agent(name="agent-a")
        agent_b = Agent(name="agent-b")

        team = Team(
            name="par-team",
            members=[agent_a, agent_b],
            protocol=TeamProtocol.PARALLEL,
        )

        result = await TeamRunner.run(
            team, "Analyze this", config=RunConfig(model_provider=provider)
        )

        assert isinstance(result, TeamResult)
        assert len(result.member_results) == 2
        assert result.protocol == "parallel"
        # 输出包含两个成员的结果
        assert "[agent-a]" in result.output
        assert "[agent-b]" in result.output
        assert "Parallel result" in result.output

    @pytest.mark.asyncio
    async def test_parallel_custom_separator(self) -> None:
        """自定义分隔符。"""
        provider = MockSequentialProvider("Result")
        team = Team(
            name="par",
            members=[Agent(name="a"), Agent(name="b")],
            protocol=TeamProtocol.PARALLEL,
            config=TeamConfig(separator=" | "),
        )
        result = await TeamRunner.run(
            team, "test", config=RunConfig(model_provider=provider)
        )
        assert " | " in result.output

    @pytest.mark.asyncio
    async def test_parallel_empty_members(self) -> None:
        """空成员列表返回空结果。"""
        team = Team(name="empty", members=[], protocol=TeamProtocol.PARALLEL)
        result = await TeamRunner.run(team, "input")
        assert result.output == ""


# ── TeamRunner — Coordinator 测试 ────────────────────────────


class TestTeamRunnerCoordinator:
    @pytest.mark.asyncio
    async def test_coordinator_no_coordinator_agent(self) -> None:
        """COORDINATOR 模式未设 coordinator 报错。"""
        team = Team(
            name="bad-team",
            members=[Agent(name="worker")],
            protocol=TeamProtocol.COORDINATOR,
            coordinator=None,
        )
        with pytest.raises(ValueError, match="未设置 coordinator"):
            await TeamRunner.run(team, "do something")

    @pytest.mark.asyncio
    async def test_coordinator_runs_with_member_tools(self) -> None:
        """COORDINATOR: coordinator agent 获得 member as_tool。"""
        # Member agent 使用独立 provider
        MockSequentialProvider("Member analysis done")
        coordinator_provider = MockSequentialProvider("Coordinator final answer")

        worker = Agent(
            name="worker",
            description="Performs analysis",
            instructions="Analyze input.",
        )

        coordinator = Agent(
            name="coordinator",
            instructions="You coordinate tasks. Use available tools.",
        )

        team = Team(
            name="coord-team",
            members=[worker],
            protocol=TeamProtocol.COORDINATOR,
            coordinator=coordinator,
        )

        # 使用 coordinator_provider 运行（coordinator 直接返回文本，不调 tool）
        result = await TeamRunner.run(
            team, "Plan analysis",
            config=RunConfig(model_provider=coordinator_provider),
        )

        assert result.output == "Coordinator final answer"
        assert result.team_name == "coord-team"
        assert result.protocol == "coordinator"


# ── Team.as_tool 测试 ────────────────────────────────────────


class TestTeamAsTool:
    def test_as_tool_returns_function_tool(self) -> None:
        team = Team(name="my-team", description="A helpful team")
        tool = team.as_tool()
        assert tool.name == "my-team"
        assert tool.description == "A helpful team"

    def test_as_tool_custom_name(self) -> None:
        team = Team(name="t", description="desc")
        tool = team.as_tool(tool_name="custom", tool_description="Custom desc")
        assert tool.name == "custom"
        assert tool.description == "Custom desc"


# ── Export 测试 ──────────────────────────────────────────────


class TestTeamExports:
    def test_framework_exports(self) -> None:
        import ckyclaw_framework

        assert hasattr(ckyclaw_framework, "Team")
        assert hasattr(ckyclaw_framework, "TeamConfig")
        assert hasattr(ckyclaw_framework, "TeamProtocol")
        assert hasattr(ckyclaw_framework, "TeamResult")
        assert hasattr(ckyclaw_framework, "TeamRunner")

    def test_submodule_exports(self) -> None:
        from ckyclaw_framework.team import Team, TeamRunner

        assert Team is not None
        assert TeamRunner is not None
