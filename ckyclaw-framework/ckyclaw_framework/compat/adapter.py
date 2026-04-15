"""OpenAI Agents SDK → CkyClaw Framework 适配器。

将 OpenAI Agents SDK 风格的 Agent / Tool / Handoff / Guardrail 定义
转换为 CkyClaw Framework 原生对象。支持两种输入格式：

1. **字典模式** — 直接传入 SDK 风格的 dict（适合 JSON 配置）
2. **对象模式** — 传入 SDK Agent 实例（若安装了 ``openai-agents``）

字段映射表
----------

============================================  =============================================
OpenAI Agents SDK                             CkyClaw Framework
============================================  =============================================
``Agent.name``                                ``Agent.name``
``Agent.instructions``                        ``Agent.instructions``
``Agent.handoff_description``                 ``Agent.description``
``Agent.model`` (str)                         ``Agent.model``
``Agent.model_settings``                      ``Agent.model_settings`` → ``ModelSettings``
``Agent.tools`` (FunctionTool list)           ``Agent.tools`` → ``[FunctionTool]``
``Agent.handoffs``                            ``Agent.handoffs`` → ``[Handoff]``
``Agent.input_guardrails``                    ``Agent.input_guardrails`` → ``[InputGuardrail]``
``Agent.output_guardrails``                   ``Agent.output_guardrails`` → ``[OutputGuardrail]``
``Agent.output_type``                         ``Agent.output_type``
``Runner.run(agent, input)``                  ``Runner.run(agent, input)``
============================================  =============================================
"""

from __future__ import annotations

import inspect
import json
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ckyclaw_framework.runner.result import RunResult
    from ckyclaw_framework.runner.run_config import RunConfig
    from ckyclaw_framework.runner.run_context import RunContext

# ---------------------------------------------------------------------------
# Tool Conversion
# ---------------------------------------------------------------------------

def from_openai_tool(sdk_tool: Any) -> FunctionTool:
    """将 OpenAI SDK FunctionTool 或等价 dict 转换为 CkyClaw FunctionTool。

    Args:
        sdk_tool: SDK FunctionTool 实例或如下格式的 dict::

            {
                "name": "search_web",
                "description": "Search the internet",
                "params_json_schema": {...},  # JSON Schema
                "on_invoke_tool": async (ctx, args_json) -> str,
            }

    Returns:
        CkyClaw ``FunctionTool`` 实例。
    """
    if isinstance(sdk_tool, dict):
        return _convert_tool_from_dict(sdk_tool)
    return _convert_tool_from_object(sdk_tool)


def _convert_tool_from_dict(d: dict[str, Any]) -> FunctionTool:
    """从字典格式转换工具。"""
    name = d.get("name", "unnamed_tool")
    description = d.get("description", "")
    schema = d.get("params_json_schema") or d.get("parameters_schema") or d.get("parameters", {})

    # 函数：优先 on_invoke_tool（SDK 风格），其次 fn（CkyClaw 原生）
    fn = d.get("on_invoke_tool") or d.get("fn")

    # 如果 fn 接收 (ctx, args_json_str)，包装为 CkyClaw 风格 (ctx, **kwargs)
    wrapped_fn = _wrap_sdk_tool_fn(fn) if fn else None

    return FunctionTool(
        name=name,
        description=description,
        fn=wrapped_fn,
        parameters_schema=schema,
    )


def _convert_tool_from_object(obj: Any) -> FunctionTool:
    """从 SDK FunctionTool 对象转换。"""
    name = getattr(obj, "name", "unnamed_tool")
    description = getattr(obj, "description", "")
    schema = getattr(obj, "params_json_schema", None) or getattr(obj, "parameters", {})

    # SDK FunctionTool 使用 on_invoke_tool
    fn = getattr(obj, "on_invoke_tool", None) or getattr(obj, "fn", None)
    wrapped_fn = _wrap_sdk_tool_fn(fn) if fn else None

    return FunctionTool(
        name=name,
        description=description,
        fn=wrapped_fn,
        parameters_schema=schema,
    )


def _wrap_sdk_tool_fn(fn: Callable[..., Any]) -> Callable[..., Any]:
    """包装 SDK 风格工具函数为 CkyClaw 兼容签名。

    SDK 工具函数签名: ``async (ctx, args_json: str) -> str``
    CkyClaw 工具函数签名: ``async (**kwargs) -> str``

    如果函数已经是 CkyClaw 风格（接收 **kwargs），直接返回。
    """
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    # SDK 风格判断：恰好 2 个 POSITIONAL_OR_KEYWORD 参数，且全部不带默认值
    positional_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.default is inspect.Parameter.empty
    ]
    if len(positional_params) == 2 and len(params) == 2:
        async def _wrapped(**kwargs: Any) -> Any:
            # 构造 JSON 字符串作为第二个参数
            args_json = json.dumps(kwargs)
            result = fn(None, args_json)
            if inspect.isawaitable(result):
                result = await result
            return result
        _wrapped.__name__ = getattr(fn, "__name__", "sdk_tool_fn")
        return _wrapped

    # 否则认为已经是 CkyClaw 风格
    return fn


# ---------------------------------------------------------------------------
# Handoff Conversion
# ---------------------------------------------------------------------------

def from_openai_handoff(sdk_handoff: Any, *, agent_cache: dict[str, Agent] | None = None) -> Handoff:
    """将 OpenAI SDK Handoff 或等价 dict 转换为 CkyClaw Handoff。

    Args:
        sdk_handoff: SDK Handoff 实例或 dict::

            {
                "agent": <sdk_agent_or_dict>,
                "tool_name": "transfer_to_triage",
                "tool_description": "Transfer to triage agent",
            }
        agent_cache: 可选，已转换 Agent 缓存，避免重复创建。

    Returns:
        CkyClaw ``Handoff`` 实例。
    """
    cache = agent_cache if agent_cache is not None else {}

    if isinstance(sdk_handoff, dict):
        target = sdk_handoff.get("agent")
        tool_name = sdk_handoff.get("tool_name")
        tool_description = sdk_handoff.get("tool_description")
    else:
        target = getattr(sdk_handoff, "agent", None)
        tool_name = getattr(sdk_handoff, "tool_name", None) or getattr(sdk_handoff, "tool_name_override", None)
        tool_description = getattr(sdk_handoff, "tool_description", None) or getattr(sdk_handoff, "tool_description_override", None)

    # 递归转换目标 Agent
    target_agent = _resolve_agent(target, cache)

    return Handoff(
        agent=target_agent,
        tool_name=tool_name,
        tool_description=tool_description,
    )


# ---------------------------------------------------------------------------
# Guardrail Conversion
# ---------------------------------------------------------------------------

def from_openai_guardrail(
    sdk_guardrail: Any,
    *,
    kind: str = "input",
) -> InputGuardrail | OutputGuardrail:
    """将 OpenAI SDK Guardrail 或等价 dict 转换为 CkyClaw Guardrail。

    Args:
        sdk_guardrail: SDK InputGuardrail/OutputGuardrail 实例或 dict::

            {
                "guardrail_function": async (ctx, agent, input) -> GuardrailFunctionOutput,
                "name": "my_guardrail",
            }
        kind: ``"input"`` 或 ``"output"``。

    Returns:
        CkyClaw ``InputGuardrail`` 或 ``OutputGuardrail``。
    """
    if isinstance(sdk_guardrail, dict):
        fn = sdk_guardrail.get("guardrail_function")
        name = sdk_guardrail.get("name", "")
    else:
        fn = getattr(sdk_guardrail, "guardrail_function", None)
        name = getattr(sdk_guardrail, "name", "")

    wrapped_fn = _wrap_guardrail_fn(fn) if fn else _noop_guardrail

    if kind == "output":
        return OutputGuardrail(guardrail_function=wrapped_fn, name=name)
    return InputGuardrail(guardrail_function=wrapped_fn, name=name)


def _wrap_guardrail_fn(fn: Callable[..., Any]) -> Callable[..., Awaitable[GuardrailResult]]:
    """包装 SDK 护栏函数为 CkyClaw 签名。

    SDK 签名: ``async (ctx, agent, input_or_output) -> GuardrailFunctionOutput``
      其中 GuardrailFunctionOutput 有 output.tripwire_triggered, output.output_info
    CkyClaw 签名: ``async (run_context, text) -> GuardrailResult``
    """
    async def _wrapped(run_context: RunContext, text: str) -> GuardrailResult:
        try:
            result = fn(run_context, run_context.agent, text)
            if inspect.isawaitable(result):
                result = await result

            # 如果返回的已经是 GuardrailResult，直接用
            if isinstance(result, GuardrailResult):
                return result
            # SDK GuardrailFunctionOutput 有 output 属性
            output = getattr(result, "output", result)
            if isinstance(output, GuardrailResult):
                return output
            if hasattr(output, "tripwire_triggered"):
                return GuardrailResult(
                    tripwire_triggered=output.tripwire_triggered,
                    message=getattr(output, "output_info", "") or "",
                )
            # 布尔值：True = 通过
            if isinstance(output, bool):
                return GuardrailResult(tripwire_triggered=not output)
            return GuardrailResult()
        except Exception as exc:
            return GuardrailResult(tripwire_triggered=True, message=str(exc))

    _wrapped.__name__ = getattr(fn, "__name__", "sdk_guardrail_fn")
    return _wrapped


async def _noop_guardrail(_ctx: Any, _text: str) -> GuardrailResult:
    """空操作护栏占位。"""
    return GuardrailResult()


# ---------------------------------------------------------------------------
# Agent Conversion
# ---------------------------------------------------------------------------

def from_openai_agent(sdk_agent: Any, *, agent_cache: dict[str, Agent] | None = None) -> Agent:
    """将 OpenAI SDK Agent 或等价 dict 转换为 CkyClaw Agent。

    支持递归转换：handoffs 中引用的子 Agent 也会被自动转换。

    Args:
        sdk_agent: SDK Agent 实例或 dict::

            {
                "name": "triage_agent",
                "instructions": "You are a triage agent...",
                "model": "gpt-4.1",
                "model_settings": {"temperature": 0.7},
                "tools": [...],
                "handoffs": [...],
                "input_guardrails": [...],
                "output_guardrails": [...],
                "output_type": SomeClass,
                "handoff_description": "Handles triage",
            }
        agent_cache: 内部用，已转换 Agent 缓存。

    Returns:
        CkyClaw ``Agent`` 实例。
    """
    cache = agent_cache if agent_cache is not None else {}
    return _resolve_agent(sdk_agent, cache)


def _resolve_agent(sdk_agent: Any, cache: dict[str, Agent]) -> Agent:
    """解析并缓存 Agent，防止循环引用。"""
    if isinstance(sdk_agent, Agent):
        return sdk_agent

    name = sdk_agent.get("name", "unnamed") if isinstance(sdk_agent, dict) else getattr(sdk_agent, "name", "unnamed")

    if name in cache:
        return cache[name]

    # 预注册占位 Agent 防循环；转换完成后原地更新属性
    placeholder = Agent(name=name)
    cache[name] = placeholder

    # 实际转换
    converted = _convert_agent(sdk_agent, cache)

    # 将转换结果属性写回占位对象，确保所有已引用的地方都看到最终版本
    for attr in (
        "name", "description", "instructions", "model", "model_settings",
        "tools", "handoffs", "input_guardrails", "output_guardrails",
        "tool_guardrails", "approval_mode", "output_type", "response_style",
    ):
        setattr(placeholder, attr, getattr(converted, attr))

    return placeholder


def _convert_agent(sdk_agent: Any, cache: dict[str, Agent]) -> Agent:
    """执行实际的 Agent 转换。"""
    if isinstance(sdk_agent, dict):
        return _convert_agent_from_dict(sdk_agent, cache)
    return _convert_agent_from_object(sdk_agent, cache)


def _convert_agent_from_dict(d: dict[str, Any], cache: dict[str, Agent]) -> Agent:
    """从字典转换 Agent。"""
    name = d.get("name", "unnamed")

    # 指令：支持 str 或 callable
    instructions = d.get("instructions", "")

    # 模型
    model = d.get("model")
    if model and not isinstance(model, str):
        model = str(model)

    # 模型设置
    model_settings = _convert_model_settings(d.get("model_settings"))

    # 工具
    tools = [from_openai_tool(t) for t in (d.get("tools") or [])]

    # Handoff
    handoffs = [from_openai_handoff(h, agent_cache=cache) for h in (d.get("handoffs") or [])]

    # 护栏
    input_guardrails = [
        from_openai_guardrail(g, kind="input")
        for g in (d.get("input_guardrails") or [])
    ]
    output_guardrails = [
        from_openai_guardrail(g, kind="output")
        for g in (d.get("output_guardrails") or [])
    ]

    # 描述
    description = d.get("handoff_description") or d.get("description", "")

    # 输出类型
    output_type = d.get("output_type")

    return Agent(
        name=name,
        description=description,
        instructions=instructions,
        model=model,
        model_settings=model_settings,
        tools=tools,
        handoffs=list(handoffs),
        input_guardrails=list(input_guardrails),  # type: ignore[arg-type]
        output_guardrails=list(output_guardrails),  # type: ignore[arg-type]
        output_type=output_type,
    )


def _convert_agent_from_object(obj: Any, cache: dict[str, Agent]) -> Agent:
    """从 SDK Agent 对象转换。"""
    name = getattr(obj, "name", "unnamed")
    instructions = getattr(obj, "instructions", "")
    model = getattr(obj, "model", None)
    if model and not isinstance(model, str):
        model = str(model)

    model_settings = _convert_model_settings(getattr(obj, "model_settings", None))

    # 工具：过滤掉非 FunctionTool 的（如 hosted tools），只转换函数工具
    raw_tools = getattr(obj, "tools", []) or []
    tools = []
    for t in raw_tools:
        with suppress(Exception):
            tools.append(from_openai_tool(t))  # 跳过无法转换的工具（如 hosted tools）

    # Handoffs
    raw_handoffs = getattr(obj, "handoffs", []) or []
    handoffs = [from_openai_handoff(h, agent_cache=cache) for h in raw_handoffs]

    # 护栏
    raw_input_guardrails = getattr(obj, "input_guardrails", []) or []
    input_guardrails = [from_openai_guardrail(g, kind="input") for g in raw_input_guardrails]
    raw_output_guardrails = getattr(obj, "output_guardrails", []) or []
    output_guardrails = [from_openai_guardrail(g, kind="output") for g in raw_output_guardrails]

    description = getattr(obj, "handoff_description", "") or getattr(obj, "description", "")
    output_type = getattr(obj, "output_type", None)

    return Agent(
        name=name,
        description=description,
        instructions=instructions,
        model=model,
        model_settings=model_settings,
        tools=tools,
        handoffs=list(handoffs),
        input_guardrails=list(input_guardrails),  # type: ignore[arg-type]
        output_guardrails=list(output_guardrails),  # type: ignore[arg-type]
        output_type=output_type,
    )


# ---------------------------------------------------------------------------
# ModelSettings Conversion
# ---------------------------------------------------------------------------

def _convert_model_settings(sdk_settings: Any) -> ModelSettings | None:
    """转换 SDK ModelSettings 为 CkyClaw ModelSettings。"""
    if sdk_settings is None:
        return None
    if isinstance(sdk_settings, ModelSettings):
        return sdk_settings
    if isinstance(sdk_settings, dict):
        return ModelSettings(
            temperature=sdk_settings.get("temperature"),
            max_tokens=sdk_settings.get("max_tokens"),
            top_p=sdk_settings.get("top_p"),
            stop=sdk_settings.get("stop"),
        )
    # SDK ModelSettings 对象
    return ModelSettings(
        temperature=getattr(sdk_settings, "temperature", None),
        max_tokens=getattr(sdk_settings, "max_tokens", None) or getattr(sdk_settings, "max_output_tokens", None),
        top_p=getattr(sdk_settings, "top_p", None),
        stop=getattr(sdk_settings, "stop", None),
    )


# ---------------------------------------------------------------------------
# SdkAgentAdapter — 高级适配器类
# ---------------------------------------------------------------------------

@dataclass
class SdkAgentAdapter:
    """OpenAI Agents SDK → CkyClaw Framework 的高级适配器。

    提供批量转换和直接运行能力::

        adapter = SdkAgentAdapter()
        agent = adapter.convert_agent(sdk_agent_dict)
        result = await adapter.run(agent, "What is the weather?")

    Attributes:
        config: 可选的 RunConfig，用于所有运行。
        agent_cache: 已转换 Agent 缓存，用于处理跨 Agent 引用。
    """

    config: RunConfig | None = None
    agent_cache: dict[str, Agent] = field(default_factory=dict)

    def convert_agent(self, sdk_agent: Any) -> Agent:
        """转换单个 SDK Agent。"""
        return from_openai_agent(sdk_agent, agent_cache=self.agent_cache)

    def convert_tool(self, sdk_tool: Any) -> FunctionTool:
        """转换单个 SDK Tool。"""
        return from_openai_tool(sdk_tool)

    def convert_handoff(self, sdk_handoff: Any) -> Handoff:
        """转换单个 SDK Handoff。"""
        return from_openai_handoff(sdk_handoff, agent_cache=self.agent_cache)

    async def run(
        self,
        agent: Agent | Any,
        input_text: str,
        *,
        max_turns: int = 10,
        config: RunConfig | None = None,
    ) -> RunResult:
        """使用 CkyClaw Runner 运行 Agent。

        如果 agent 不是 CkyClaw Agent 实例，会先转换。

        Args:
            agent: CkyClaw Agent 或 SDK Agent。
            input_text: 用户输入文本。
            max_turns: 最大执行轮次。
            config: 运行配置（覆盖实例级 config）。

        Returns:
            CkyClaw ``RunResult``。
        """
        if not isinstance(agent, Agent):
            agent = self.convert_agent(agent)

        effective_config = config or self.config
        return await Runner.run(
            agent=agent,
            input=input_text,
            config=effective_config,
            max_turns=max_turns,
        )

    def run_sync(
        self,
        agent: Agent | Any,
        input_text: str,
        *,
        max_turns: int = 10,
        config: RunConfig | None = None,
    ) -> RunResult:
        """同步运行 Agent（兼容非异步环境）。"""
        if not isinstance(agent, Agent):
            agent = self.convert_agent(agent)

        effective_config = config or self.config
        return Runner.run_sync(
            agent=agent,
            input=input_text,
            config=effective_config,
            max_turns=max_turns,
        )
