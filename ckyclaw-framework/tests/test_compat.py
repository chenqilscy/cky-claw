"""CkyClaw Framework — compat 兼容层测试。

覆盖场景：
- Tool 转换（dict / 对象 / SDK 签名包装）
- Handoff 转换 + 递归 Agent 解析
- Guardrail 转换（input / output / bool / 异常）
- Agent 转换（dict / 对象 / 嵌套 handoffs / 循环引用）
- ModelSettings 转换
- SdkAgentAdapter 高级 API
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.compat.adapter import (
    SdkAgentAdapter,
    from_openai_agent,
    from_openai_guardrail,
    from_openai_handoff,
    from_openai_tool,
    _convert_model_settings,
    _wrap_sdk_tool_fn,
)
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.tools.function_tool import FunctionTool


# ═══════════════════════════════════════════════════════════════════
# Tool Conversion
# ═══════════════════════════════════════════════════════════════════


class TestFromOpenaiTool:
    """from_openai_tool 测试。"""

    def test_dict_basic(self) -> None:
        """基本 dict → FunctionTool 转换。"""
        tool = from_openai_tool({
            "name": "search",
            "description": "Search the web",
            "params_json_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        })
        assert isinstance(tool, FunctionTool)
        assert tool.name == "search"
        assert tool.description == "Search the web"
        assert tool.parameters_schema["type"] == "object"

    def test_dict_with_on_invoke_tool(self) -> None:
        """SDK 风格 on_invoke_tool 函数包装。"""
        async def my_fn(ctx: Any, args_json: str) -> str:
            return f"called with {args_json}"

        tool = from_openai_tool({
            "name": "my_tool",
            "on_invoke_tool": my_fn,
        })
        assert tool.fn is not None
        assert tool.name == "my_tool"

    def test_dict_with_fn_field(self) -> None:
        """CkyClaw 原生 fn 字段也接受。"""
        async def native_fn(**kwargs: Any) -> str:
            return "ok"

        tool = from_openai_tool({
            "name": "native",
            "fn": native_fn,
        })
        assert tool.fn is not None

    def test_dict_no_fn(self) -> None:
        """无函数时 fn 为 None。"""
        tool = from_openai_tool({"name": "placeholder"})
        assert tool.fn is None

    def test_dict_defaults(self) -> None:
        """空 dict 使用默认值。"""
        tool = from_openai_tool({})
        assert tool.name == "unnamed_tool"
        assert tool.description == ""

    def test_dict_parameters_alias(self) -> None:
        """parameters 别名也接受。"""
        schema = {"type": "object", "properties": {}}
        tool = from_openai_tool({"name": "t", "parameters": schema})
        assert tool.parameters_schema == schema

    def test_object_conversion(self) -> None:
        """从对象属性转换。"""
        @dataclass
        class SdkTool:
            name: str = "obj_tool"
            description: str = "Object tool"
            params_json_schema: dict = None  # type: ignore[assignment]

            def __post_init__(self) -> None:
                if self.params_json_schema is None:
                    self.params_json_schema = {"type": "object"}

        tool = from_openai_tool(SdkTool())
        assert tool.name == "obj_tool"
        assert tool.description == "Object tool"

    def test_object_with_on_invoke_tool(self) -> None:
        """对象的 on_invoke_tool 属性。"""
        async def invoke(ctx: Any, args: str) -> str:
            return "ok"

        class MockSdkTool:
            name = "mock_tool"
            description = ""
            params_json_schema = {}
            on_invoke_tool = invoke

        tool = from_openai_tool(MockSdkTool())
        assert tool.fn is not None


class TestWrapSdkToolFn:
    """_wrap_sdk_tool_fn 签名适配测试。"""

    @pytest.mark.asyncio
    async def test_sdk_style_two_args(self) -> None:
        """SDK 风格 (ctx, args_json) → CkyClaw **kwargs。"""
        async def sdk_fn(ctx: Any, args_json: str) -> str:
            data = json.loads(args_json)
            return f"q={data['query']}"

        wrapped = _wrap_sdk_tool_fn(sdk_fn)
        result = await wrapped(query="hello")
        assert result == "q=hello"

    @pytest.mark.asyncio
    async def test_sync_sdk_fn(self) -> None:
        """同步 SDK 函数也能包装。"""
        def sync_fn(ctx: Any, args_json: str) -> str:
            data = json.loads(args_json)
            return data.get("x", "none")

        wrapped = _wrap_sdk_tool_fn(sync_fn)
        result = await wrapped(x="42")
        assert result == "42"

    def test_ckyclaw_style_passthrough(self) -> None:
        """CkyClaw 原生风格（非两参数）直接返回。"""
        async def native_fn(query: str, limit: int = 10) -> str:
            return f"{query}:{limit}"

        result = _wrap_sdk_tool_fn(native_fn)
        assert result is native_fn

    def test_kwargs_only_passthrough(self) -> None:
        """**kwargs 签名直接返回。"""
        async def kw_fn(**kwargs: Any) -> str:
            return str(kwargs)

        result = _wrap_sdk_tool_fn(kw_fn)
        assert result is kw_fn


# ═══════════════════════════════════════════════════════════════════
# Handoff Conversion
# ═══════════════════════════════════════════════════════════════════


class TestFromOpenaiHandoff:
    """from_openai_handoff 测试。"""

    def test_dict_basic(self) -> None:
        """基本 dict → Handoff。"""
        handoff = from_openai_handoff({
            "agent": {"name": "target_agent", "instructions": "Do stuff"},
            "tool_name": "transfer_to_target",
            "tool_description": "Transfer to target agent",
        })
        assert isinstance(handoff, Handoff)
        assert handoff.agent.name == "target_agent"
        assert handoff.tool_name == "transfer_to_target"
        assert handoff.tool_description == "Transfer to target agent"

    def test_dict_with_ckyclaw_agent(self) -> None:
        """目标已经是 CkyClaw Agent。"""
        target = Agent(name="existing")
        handoff = from_openai_handoff({"agent": target})
        assert handoff.agent is target

    def test_object_conversion(self) -> None:
        """从对象属性转换。"""
        class SdkHandoff:
            agent = {"name": "sub", "instructions": "sub agent"}
            tool_name_override = "go_to_sub"
            tool_description = None

        handoff = from_openai_handoff(SdkHandoff())
        assert handoff.agent.name == "sub"
        assert handoff.tool_name == "go_to_sub"

    def test_recursive_agent_conversion(self) -> None:
        """递归转换嵌套 Agent。"""
        handoff = from_openai_handoff({
            "agent": {
                "name": "level1",
                "handoffs": [{"agent": {"name": "level2"}}],
            },
        })
        assert handoff.agent.name == "level1"
        assert len(handoff.agent.handoffs) == 1
        inner = handoff.agent.handoffs[0]
        assert isinstance(inner, Handoff)
        assert inner.agent.name == "level2"

    def test_agent_cache_prevents_duplicate(self) -> None:
        """缓存避免重复创建。"""
        cache: dict[str, Agent] = {}
        h1 = from_openai_handoff({"agent": {"name": "shared"}}, agent_cache=cache)
        h2 = from_openai_handoff({"agent": {"name": "shared"}}, agent_cache=cache)
        assert h1.agent is h2.agent


# ═══════════════════════════════════════════════════════════════════
# Guardrail Conversion
# ═══════════════════════════════════════════════════════════════════


class TestFromOpenaiGuardrail:
    """from_openai_guardrail 测试。"""

    def test_input_guardrail_dict(self) -> None:
        """dict → InputGuardrail。"""
        guard = from_openai_guardrail({
            "name": "no_sql_injection",
            "guardrail_function": lambda ctx, agent, text: None,
        }, kind="input")
        assert isinstance(guard, InputGuardrail)
        assert guard.name == "no_sql_injection"

    def test_output_guardrail_dict(self) -> None:
        """dict → OutputGuardrail。"""
        guard = from_openai_guardrail({
            "name": "safe_output",
        }, kind="output")
        assert isinstance(guard, OutputGuardrail)
        assert guard.name == "safe_output"

    def test_no_fn_uses_noop(self) -> None:
        """无 guardrail_function 时使用 noop。"""
        guard = from_openai_guardrail({"name": "placeholder"})
        assert isinstance(guard, InputGuardrail)
        assert guard.guardrail_function is not None

    @pytest.mark.asyncio
    async def test_guardrail_bool_return(self) -> None:
        """护栏函数返回 bool → GuardrailResult。"""
        async def check_fn(ctx: Any, agent: Any, text: str) -> bool:
            return "bad" not in text

        guard = from_openai_guardrail({"guardrail_function": check_fn})
        assert isinstance(guard, InputGuardrail)

        # 模拟 RunContext
        mock_ctx = type("MockCtx", (), {"agent": Agent(name="test")})()

        result = await guard.guardrail_function(mock_ctx, "good text")
        assert isinstance(result, GuardrailResult)
        assert result.tripwire_triggered is False

        result = await guard.guardrail_function(mock_ctx, "bad text")
        assert result.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_guardrail_exception_handling(self) -> None:
        """护栏函数异常 → tripwire_triggered=True。"""
        async def failing_fn(ctx: Any, agent: Any, text: str) -> bool:
            raise ValueError("oops")

        guard = from_openai_guardrail({"guardrail_function": failing_fn})
        mock_ctx = type("MockCtx", (), {"agent": Agent(name="test")})()
        result = await guard.guardrail_function(mock_ctx, "anything")
        assert result.tripwire_triggered is True
        assert "oops" in result.message

    @pytest.mark.asyncio
    async def test_guardrail_result_passthrough(self) -> None:
        """护栏函数直接返回 GuardrailResult → 透传。"""
        async def direct_fn(ctx: Any, agent: Any, text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="blocked")

        guard = from_openai_guardrail({"guardrail_function": direct_fn})
        mock_ctx = type("MockCtx", (), {"agent": Agent(name="test")})()
        result = await guard.guardrail_function(mock_ctx, "text")
        assert result.tripwire_triggered is True
        assert result.message == "blocked"

    def test_object_guardrail(self) -> None:
        """从 SDK 对象转换。"""
        class SdkGuardrail:
            name = "obj_guard"
            guardrail_function = None

        guard = from_openai_guardrail(SdkGuardrail())
        assert guard.name == "obj_guard"


# ═══════════════════════════════════════════════════════════════════
# Agent Conversion
# ═══════════════════════════════════════════════════════════════════


class TestFromOpenaiAgent:
    """from_openai_agent 测试。"""

    def test_basic_dict(self) -> None:
        """基本 dict → Agent。"""
        agent = from_openai_agent({
            "name": "triage",
            "instructions": "You are a triage agent.",
            "model": "gpt-4.1",
        })
        assert isinstance(agent, Agent)
        assert agent.name == "triage"
        assert agent.instructions == "You are a triage agent."
        assert agent.model == "gpt-4.1"

    def test_full_dict(self) -> None:
        """完整字段 dict 转换。"""
        async def guard_fn(ctx: Any, agent: Any, text: str) -> bool:
            return True

        agent = from_openai_agent({
            "name": "full_agent",
            "instructions": "Do everything",
            "model": "gpt-4.1-mini",
            "model_settings": {"temperature": 0.5, "max_tokens": 1000},
            "tools": [{"name": "tool1", "description": "Tool 1"}],
            "handoffs": [{"agent": {"name": "helper"}}],
            "input_guardrails": [{"name": "g1", "guardrail_function": guard_fn}],
            "output_guardrails": [{"name": "g2", "guardrail_function": guard_fn}],
            "handoff_description": "Full agent description",
            "output_type": str,
        })
        assert agent.name == "full_agent"
        assert agent.model == "gpt-4.1-mini"
        assert agent.description == "Full agent description"
        assert agent.output_type is str
        assert agent.model_settings is not None
        assert agent.model_settings.temperature == 0.5
        assert agent.model_settings.max_tokens == 1000
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "tool1"
        assert len(agent.handoffs) == 1
        assert len(agent.input_guardrails) == 1
        assert len(agent.output_guardrails) == 1

    def test_ckyclaw_agent_passthrough(self) -> None:
        """CkyClaw Agent 直接透传。"""
        original = Agent(name="native")
        result = from_openai_agent(original)
        assert result is original

    def test_non_str_model(self) -> None:
        """非字符串 model 自动转 str。"""
        agent = from_openai_agent({"name": "a", "model": 12345})
        assert agent.model == "12345"

    def test_model_none(self) -> None:
        """model 为 None。"""
        agent = from_openai_agent({"name": "a"})
        assert agent.model is None

    def test_empty_lists(self) -> None:
        """空列表字段。"""
        agent = from_openai_agent({"name": "empty"})
        assert agent.tools == []
        assert agent.handoffs == []
        assert agent.input_guardrails == []
        assert agent.output_guardrails == []

    def test_description_fallback(self) -> None:
        """description 字段作为 handoff_description 的备选。"""
        agent = from_openai_agent({"name": "a", "description": "desc"})
        assert agent.description == "desc"

    def test_handoff_description_priority(self) -> None:
        """handoff_description 优先于 description。"""
        agent = from_openai_agent({
            "name": "a",
            "handoff_description": "hd",
            "description": "d",
        })
        assert agent.description == "hd"

    def test_object_conversion(self) -> None:
        """SDK Agent 对象转换。"""
        @dataclass
        class SdkAgent:
            name: str = "sdk_agent"
            instructions: str = "SDK instructions"
            model: str = "gpt-4.1"
            model_settings: Any = None
            tools: list = None  # type: ignore[assignment]
            handoffs: list = None  # type: ignore[assignment]
            input_guardrails: list = None  # type: ignore[assignment]
            output_guardrails: list = None  # type: ignore[assignment]
            handoff_description: str = "SDK agent desc"
            output_type: type | None = None

            def __post_init__(self) -> None:
                if self.tools is None:
                    self.tools = []
                if self.handoffs is None:
                    self.handoffs = []
                if self.input_guardrails is None:
                    self.input_guardrails = []
                if self.output_guardrails is None:
                    self.output_guardrails = []

        agent = from_openai_agent(SdkAgent())
        assert agent.name == "sdk_agent"
        assert agent.instructions == "SDK instructions"
        assert agent.description == "SDK agent desc"

    def test_circular_reference(self) -> None:
        """循环引用不会无限递归。"""
        # Agent A handoff → Agent B handoff → Agent A
        cache: dict[str, Agent] = {}
        sdk_a = {
            "name": "A",
            "handoffs": [{"agent": {"name": "B", "handoffs": [{"agent": {"name": "A"}}]}}],
        }
        agent_a = from_openai_agent(sdk_a, agent_cache=cache)
        assert agent_a.name == "A"
        # B 的 handoff 应该引用缓存中的 A
        assert len(agent_a.handoffs) == 1
        agent_b = agent_a.handoffs[0].agent
        assert agent_b.name == "B"

    def test_nested_tools(self) -> None:
        """嵌套 Agent 的 tools 也能正确转换。"""
        agent = from_openai_agent({
            "name": "parent",
            "handoffs": [{
                "agent": {
                    "name": "child",
                    "tools": [{"name": "child_tool", "description": "Child's tool"}],
                },
            }],
        })
        child = agent.handoffs[0].agent
        assert len(child.tools) == 1
        assert child.tools[0].name == "child_tool"


# ═══════════════════════════════════════════════════════════════════
# ModelSettings Conversion
# ═══════════════════════════════════════════════════════════════════


class TestConvertModelSettings:
    """_convert_model_settings 测试。"""

    def test_none_returns_none(self) -> None:
        """None → None。"""
        assert _convert_model_settings(None) is None

    def test_ckyclaw_instance_passthrough(self) -> None:
        """CkyClaw ModelSettings 直接透传。"""
        ms = ModelSettings(temperature=0.7)
        assert _convert_model_settings(ms) is ms

    def test_dict_conversion(self) -> None:
        """dict → ModelSettings。"""
        ms = _convert_model_settings({
            "temperature": 0.8,
            "max_tokens": 2000,
            "top_p": 0.9,
            "stop": ["\n"],
        })
        assert ms is not None
        assert ms.temperature == 0.8
        assert ms.max_tokens == 2000
        assert ms.top_p == 0.9
        assert ms.stop == ["\n"]

    def test_dict_partial(self) -> None:
        """部分字段 dict。"""
        ms = _convert_model_settings({"temperature": 0.5})
        assert ms is not None
        assert ms.temperature == 0.5
        assert ms.max_tokens is None

    def test_object_with_max_output_tokens(self) -> None:
        """SDK 对象的 max_output_tokens → max_tokens。"""
        class SdkSettings:
            temperature = 0.7
            max_tokens = None
            max_output_tokens = 4096
            top_p = None
            stop = None

        ms = _convert_model_settings(SdkSettings())
        assert ms is not None
        assert ms.max_tokens == 4096


# ═══════════════════════════════════════════════════════════════════
# SdkAgentAdapter
# ═══════════════════════════════════════════════════════════════════


class TestSdkAgentAdapter:
    """SdkAgentAdapter 高级 API 测试。"""

    def test_convert_agent(self) -> None:
        """convert_agent 正确转换。"""
        adapter = SdkAgentAdapter()
        agent = adapter.convert_agent({"name": "a", "instructions": "test"})
        assert isinstance(agent, Agent)
        assert agent.name == "a"

    def test_convert_tool(self) -> None:
        """convert_tool 正确转换。"""
        adapter = SdkAgentAdapter()
        tool = adapter.convert_tool({"name": "t", "description": "d"})
        assert isinstance(tool, FunctionTool)

    def test_convert_handoff(self) -> None:
        """convert_handoff 正确转换。"""
        adapter = SdkAgentAdapter()
        handoff = adapter.convert_handoff({
            "agent": {"name": "x"},
            "tool_name": "go",
        })
        assert isinstance(handoff, Handoff)

    def test_agent_cache_shared(self) -> None:
        """同一 adapter 实例共享缓存。"""
        adapter = SdkAgentAdapter()
        adapter.convert_agent({"name": "shared"})
        adapter.convert_agent({"name": "shared"})
        assert "shared" in adapter.agent_cache

    def test_default_config_none(self) -> None:
        """默认 config 为 None。"""
        adapter = SdkAgentAdapter()
        assert adapter.config is None

    def test_custom_config(self) -> None:
        """可传入自定义 RunConfig。"""
        from ckyclaw_framework.runner.run_config import RunConfig
        config = RunConfig(tracing_enabled=False)
        adapter = SdkAgentAdapter(config=config)
        assert adapter.config is config

    def test_convert_already_ckyclaw(self) -> None:
        """CkyClaw Agent 传入 convert_agent 直接透传。"""
        adapter = SdkAgentAdapter()
        original = Agent(name="native")
        result = adapter.convert_agent(original)
        assert result is original


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界场景测试。"""

    def test_from_openai_tool_ckyclaw_function_tool(self) -> None:
        """传入 CkyClaw FunctionTool 对象也能正常转换。"""
        original = FunctionTool(name="native_t", description="d")
        converted = from_openai_tool(original)
        assert converted.name == "native_t"

    def test_agent_with_callable_instructions(self) -> None:
        """callable instructions 直接透传。"""
        def dynamic_instructions() -> str:
            return "dynamic"

        agent = from_openai_agent({
            "name": "dynamic",
            "instructions": dynamic_instructions,
        })
        assert agent.instructions is dynamic_instructions

    def test_tool_conversion_failure_skipped(self) -> None:
        """对象模式下无法转换的工具被跳过。"""
        class BadTool:
            """无 name 属性的工具。"""
            pass

        # 不应抛异常（from_openai_tool 对对象也有默认处理）
        tool = from_openai_tool(BadTool())
        assert tool.name == "unnamed_tool"

    @pytest.mark.asyncio
    async def test_noop_guardrail(self) -> None:
        """无 fn 护栏使用 noop，不触发。"""
        guard = from_openai_guardrail({})
        mock_ctx = type("MockCtx", (), {"agent": Agent(name="test")})()
        result = await guard.guardrail_function(mock_ctx, "anything")
        assert isinstance(result, GuardrailResult)
        assert result.tripwire_triggered is False

    def test_from_openai_agent_unnamed(self) -> None:
        """空 dict Agent 使用默认名。"""
        agent = from_openai_agent({})
        assert agent.name == "unnamed"
