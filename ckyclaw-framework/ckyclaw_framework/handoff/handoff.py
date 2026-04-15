"""Handoff 声明式定义与 InputFilter 类型。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.model.message import Message

# InputFilter: 接收当前消息历史，返回过滤后的消息历史
InputFilter = Callable[["list[Message]"], "list[Message]"]


@dataclass
class Handoff:
    """Agent 间的控制转移定义。

    使用场景：
        specialist = Agent(name="specialist", ...)
        triage = Agent(
            name="triage",
            handoffs=[
                Handoff(
                    agent=specialist,
                    input_filter=lambda msgs: msgs[-5:],  # 只保留最近 5 条
                ),
            ],
        )
    """

    agent: Agent
    """目标 Agent"""

    tool_name: str | None = None
    """暴露给 LLM 的工具名称（默认: transfer_to_{agent.name}）"""

    tool_description: str | None = None
    """工具描述（默认使用 agent.description）"""

    input_filter: InputFilter | None = None
    """消息历史过滤器：Handoff 时过滤传递给目标 Agent 的消息历史"""

    input_type: type | None = None
    """Handoff 输入类型（Pydantic BaseModel 子类）。
    设置后 LLM 在 Handoff 时必须提供符合此 schema 的结构化参数（如 reason、priority）。"""

    @property
    def resolved_tool_name(self) -> str:
        """实际暴露的工具名称。"""
        return self.tool_name or f"transfer_to_{self.agent.name}"

    @property
    def resolved_tool_description(self) -> str:
        """实际暴露的工具描述。"""
        return self.tool_description or self.agent.description or f"Transfer to {self.agent.name}"
