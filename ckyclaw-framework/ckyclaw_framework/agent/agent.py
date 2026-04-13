"""Agent 声明式定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Union

if TYPE_CHECKING:
    from ckyclaw_framework.approval.mode import ApprovalMode
    from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
    from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
    from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
    from ckyclaw_framework.handoff.handoff import Handoff
    from ckyclaw_framework.model.settings import ModelSettings
    from ckyclaw_framework.runner.run_config import RunConfig
    from ckyclaw_framework.runner.run_context import RunContext
    from ckyclaw_framework.tools.function_tool import FunctionTool

# Dynamic Instructions 类型：支持 str、sync callable、async callable
InstructionsType = Union[str, Callable[["RunContext"], str], Callable[["RunContext"], Awaitable[str]]]


@dataclass
class Agent:
    """Agent 声明式定义。Agent 不是进程——它是配置。"""

    name: str
    """Agent 唯一标识（小写字母、数字、连字符）"""

    description: str = ""
    """Agent 功能描述（同时用于 Handoff/as_tool 时的 LLM 提示）"""

    instructions: InstructionsType = ""
    """行为指令（SOUL.md 内容）。支持字符串、同步函数或异步函数。

    - str: 静态指令文本
    - Callable[[RunContext], str]: 同步动态指令
    - Callable[[RunContext], Awaitable[str]]: 异步动态指令
    """

    model: str | None = None
    """LLM 模型标识。None 时使用 RunConfig 默认模型。"""

    model_settings: ModelSettings | None = None
    """模型参数（temperature、max_tokens 等）"""

    tools: list[FunctionTool] = field(default_factory=list)
    """可调用的工具列表"""

    handoffs: list[Agent | Handoff] = field(default_factory=list)
    """可移交的目标列表。支持 Agent（简写）或 Handoff（完整配置）。"""

    input_guardrails: list[InputGuardrail] = field(default_factory=list)
    """输入安全护栏列表。在首次 LLM 调用前执行检测。"""

    output_guardrails: list[OutputGuardrail] = field(default_factory=list)
    """输出安全护栏列表。在 LLM 返回 final_output 后、构建 RunResult 前执行检测。"""

    tool_guardrails: list[ToolGuardrail] = field(default_factory=list)
    """工具安全护栏列表。在工具调用前（before）/后（after）执行检测。
    触发 Tripwire 时不中断 Run，而是返回错误消息给 LLM。"""

    approval_mode: ApprovalMode | None = None
    """审批模式。None 时使用 RunConfig 默认模式。"""

    output_type: type | None = None
    """结构化输出类型（Pydantic BaseModel 子类）"""

    response_style: str | None = None
    """输出风格标识。内置支持 "concise"（基于 talk-normal 的简洁风格）。
    None 表示不启用任何输出风格修饰。"""

    def as_tool(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
        config: RunConfig | None = None,
        condition: Callable[[RunContext], bool] | None = None,
    ) -> FunctionTool:
        """将此 Agent 包装为 Tool，供 Manager Agent 调用。

        Agent-as-Tool 场景下，Manager Agent 通过 tool_call 调用子 Agent。
        子 Agent 使用独立的消息历史运行，最终输出作为 tool_result 返回。

        Args:
            tool_name: 工具名称（默认 agent.name）
            tool_description: 工具描述（默认 agent.description）
            config: 子 Agent 运行配置（默认 None，使用默认 RunConfig）
            condition: 条件启用函数。返回 False 时工具不暴露给 LLM。

        Returns:
            FunctionTool 实例
        """
        from ckyclaw_framework.tools.function_tool import FunctionTool

        agent = self
        inner_config = config

        async def _agent_tool_fn(input: str) -> str:
            from ckyclaw_framework.runner.runner import Runner

            result = await Runner.run(agent, input, config=inner_config)
            output = result.output
            if isinstance(output, str):
                return output
            # 结构化输出：序列化为 JSON 字符串作为 tool result
            if hasattr(output, "model_dump_json"):
                return str(output.model_dump_json())
            return str(output)

        name = tool_name or self.name
        description = tool_description or self.description or f"Run agent '{self.name}'"

        return FunctionTool(
            name=name,
            description=description,
            fn=_agent_tool_fn,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Input message to the agent",
                    },
                },
                "required": ["input"],
            },
            condition=condition,
        )

    @classmethod
    def from_yaml(cls, path: str) -> Agent:
        """从 YAML 文件加载 Agent 定义。"""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Agent:
        """从字典加载 Agent 定义。"""
        raise NotImplementedError
