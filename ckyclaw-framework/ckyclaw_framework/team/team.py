"""Team — 团队声明式定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.runner.run_config import RunConfig

from ckyclaw_framework.team.protocol import TeamProtocol


@dataclass
class TeamConfig:
    """团队运行配置。"""

    max_rounds: int = 1
    """轮次上限（SEQUENTIAL / COORDINATOR 使用）。"""

    timeout: float | None = None
    """全局超时（秒）。None 表示不限制。"""

    separator: str = "\n\n---\n\n"
    """PARALLEL / BROADCAST 模式下多输出的合并分隔符。"""


@dataclass
class Team:
    """Agent 团队声明式定义。

    Team 不是进程——它是配置。描述一组 Agent 的协作方式。
    """

    name: str
    """团队唯一标识。"""

    members: list[Agent] = field(default_factory=list)
    """团队成员 Agent 列表。"""

    protocol: TeamProtocol = TeamProtocol.SEQUENTIAL
    """协作协议。"""

    config: TeamConfig = field(default_factory=TeamConfig)
    """团队运行配置。"""

    coordinator: Agent | None = None
    """协调者 Agent（COORDINATOR 模式必须设置）。
    coordinator 通过 as_tool 机制调用 members。"""

    description: str = ""
    """团队描述。"""

    def as_tool(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
        run_config: RunConfig | None = None,
    ):
        """将 Team 包装为 FunctionTool，供其他 Agent 调用。"""
        from ckyclaw_framework.tools.function_tool import FunctionTool

        _name = tool_name or self.name
        _desc = tool_description or self.description or f"Run team '{self.name}'"

        async def _run_team(input_text: str) -> str:
            from ckyclaw_framework.team.team_runner import TeamRunner

            result = await TeamRunner.run(self, input_text, config=run_config)
            return result.output

        return FunctionTool(
            name=_name,
            description=_desc,
            fn=_run_team,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_text": {"type": "string", "description": "团队任务输入"},
                },
                "required": ["input_text"],
            },
        )
