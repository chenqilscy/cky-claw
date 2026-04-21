"""TeamRunner — 团队运行引擎。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kasaya.runner.result import RunResult
    from kasaya.runner.run_config import RunConfig
    from kasaya.team.team import Team

from kasaya.runner.runner import Runner
from kasaya.team.protocol import TeamProtocol

logger = logging.getLogger(__name__)


@dataclass
class TeamResult:
    """团队执行结果。"""

    output: str
    """最终合并输出。"""

    member_results: list[RunResult] = field(default_factory=list)
    """各成员 Agent 的执行结果。"""

    team_name: str = ""
    """团队名称。"""

    protocol: str = ""
    """使用的协作协议。"""

    total_token_usage: dict[str, int] = field(default_factory=dict)
    """汇总 token 消耗。"""


def _sum_token_usage(results: list[RunResult]) -> dict[str, int]:
    """汇总多个 RunResult 的 token 消耗。"""
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for r in results:
        if r.token_usage:
            total["prompt_tokens"] += r.token_usage.prompt_tokens
            total["completion_tokens"] += r.token_usage.completion_tokens
            total["total_tokens"] += r.token_usage.total_tokens
    return total


class TeamRunner:
    """团队运行器。根据 Team.protocol 编排多 Agent 协作。"""

    @staticmethod
    async def run(
        team: Team,
        input_data: str,
        *,
        config: RunConfig | None = None,
    ) -> TeamResult:
        """运行 Agent 团队。

        Args:
            team: 团队定义。
            input_data: 用户输入。
            config: 运行配置（传递给每个 member Agent）。

        Returns:
            TeamResult 包含合并输出和各成员结果。
        """
        if team.protocol == TeamProtocol.SEQUENTIAL:
            return await TeamRunner._run_sequential(team, input_data, config)
        elif team.protocol == TeamProtocol.PARALLEL:
            return await TeamRunner._run_parallel(team, input_data, config)
        elif team.protocol == TeamProtocol.COORDINATOR:
            return await TeamRunner._run_coordinator(team, input_data, config)
        else:
            raise ValueError(f"未支持的团队协议: {team.protocol}")

    @staticmethod
    async def _run_sequential(
        team: Team,
        input_data: str,
        config: RunConfig | None,
    ) -> TeamResult:
        """SEQUENTIAL：成员按顺序执行，上一个输出作为下一个输入。"""
        if not team.members:
            return TeamResult(output="", team_name=team.name, protocol=team.protocol.value)

        # 取消令牌：用父级 token 为每个成员创建子 token
        parent_token = config.cancel_token if config else None

        current_input = input_data
        all_results: list[RunResult] = []

        for agent in team.members:
            # 每次循环前检查取消
            if parent_token is not None:
                parent_token.check()

            logger.info("Team '%s' sequential: running agent '%s'", team.name, agent.name)

            # 为每个成员创建子令牌
            member_config = config
            if parent_token is not None and config is not None:
                child_token = parent_token.create_child()
                member_config = replace(config, cancel_token=child_token)

            result = await Runner.run(agent, current_input, config=member_config)
            all_results.append(result)
            # 下一个 agent 的输入是当前 agent 的输出
            current_input = str(result.output)

        return TeamResult(
            output=current_input,
            member_results=all_results,
            team_name=team.name,
            protocol=team.protocol.value,
            total_token_usage=_sum_token_usage(all_results),
        )

    @staticmethod
    async def _run_parallel(
        team: Team,
        input_data: str,
        config: RunConfig | None,
    ) -> TeamResult:
        """PARALLEL：所有成员并发执行同一输入，合并输出。"""
        if not team.members:
            return TeamResult(output="", team_name=team.name, protocol=team.protocol.value)

        # 取消令牌：父级 token 为每个并行成员创建子 token
        parent_token = config.cancel_token if config else None
        if parent_token is not None:
            parent_token.check()

        all_results: list[RunResult] = []

        async with asyncio.TaskGroup() as tg:
            tasks = []
            for agent in team.members:
                logger.info("Team '%s' parallel: dispatching agent '%s'", team.name, agent.name)
                # 为每个并行成员创建子令牌
                member_config = config
                if parent_token is not None and config is not None:
                    child_token = parent_token.create_child()
                    member_config = replace(config, cancel_token=child_token)
                task = tg.create_task(Runner.run(agent, input_data, config=member_config))
                tasks.append((agent.name, task))

        # TaskGroup 确保所有任务完成后才到这里
        for _agent_name, task in tasks:
            all_results.append(task.result())

        # 合并所有输出
        sep = team.config.separator
        merged = sep.join(
            f"[{r.last_agent_name or 'unknown'}]\n{r.output}"
            for r in all_results
        )

        return TeamResult(
            output=merged,
            member_results=all_results,
            team_name=team.name,
            protocol=team.protocol.value,
            total_token_usage=_sum_token_usage(all_results),
        )

    @staticmethod
    async def _run_coordinator(
        team: Team,
        input_data: str,
        config: RunConfig | None,
    ) -> TeamResult:
        """COORDINATOR：coordinator Agent 通过 as_tool 调用 members。"""
        if team.coordinator is None:
            raise ValueError(f"Team '{team.name}' 使用 COORDINATOR 协议但未设置 coordinator Agent")

        # 将所有 members 作为 tools 注入 coordinator
        from kasaya.agent.agent import Agent

        coordinator = team.coordinator
        member_tools = [m.as_tool() for m in team.members]

        # 创建一个增强版 coordinator，携带 member tools
        enhanced = Agent(
            name=coordinator.name,
            description=coordinator.description,
            instructions=coordinator.instructions,
            model=coordinator.model,
            model_settings=coordinator.model_settings,
            tools=list(coordinator.tools) + member_tools,
            handoffs=coordinator.handoffs,
            input_guardrails=coordinator.input_guardrails,
            output_guardrails=coordinator.output_guardrails,
            tool_guardrails=coordinator.tool_guardrails,
            approval_mode=coordinator.approval_mode,
            output_type=coordinator.output_type,
        )

        logger.info("Team '%s' coordinator: running coordinator '%s' with %d member tools",
                     team.name, coordinator.name, len(member_tools))

        # 为 coordinator 创建子令牌
        parent_token = config.cancel_token if config else None
        member_config = config
        if parent_token is not None and config is not None:
            parent_token.check()
            child_token = parent_token.create_child()
            member_config = replace(config, cancel_token=child_token)

        result = await Runner.run(enhanced, input_data, config=member_config)

        return TeamResult(
            output=str(result.output),
            member_results=[result],
            team_name=team.name,
            protocol=team.protocol.value,
            total_token_usage=_sum_token_usage([result]),
        )
