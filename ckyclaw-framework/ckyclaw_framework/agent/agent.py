"""Agent 声明式定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ckyclaw_framework.handoff.handoff import Handoff
    from ckyclaw_framework.model.settings import ModelSettings
    from ckyclaw_framework.runner.run_context import RunContext
    from ckyclaw_framework.tools.function_tool import FunctionTool


@dataclass
class Agent:
    """Agent 声明式定义。Agent 不是进程——它是配置。"""

    name: str
    """Agent 唯一标识（小写字母、数字、连字符）"""

    description: str = ""
    """Agent 功能描述（同时用于 Handoff/as_tool 时的 LLM 提示）"""

    instructions: str | Callable[[RunContext], str] = ""
    """行为指令（SOUL.md 内容）。支持字符串或动态函数。"""

    model: str | None = None
    """LLM 模型标识。None 时使用 RunConfig 默认模型。"""

    model_settings: ModelSettings | None = None
    """模型参数（temperature、max_tokens 等）"""

    tools: list[FunctionTool] = field(default_factory=list)
    """可调用的工具列表"""

    handoffs: list[Agent | Handoff] = field(default_factory=list)
    """可移交的目标列表。支持 Agent（简写）或 Handoff（完整配置）。"""

    output_type: type | None = None
    """结构化输出类型（Pydantic BaseModel 子类）"""

    @classmethod
    def from_yaml(cls, path: str) -> Agent:
        """从 YAML 文件加载 Agent 定义。"""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Agent:
        """从字典加载 Agent 定义。"""
        raise NotImplementedError
