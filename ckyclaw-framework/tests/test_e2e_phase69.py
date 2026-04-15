"""Phase 6.9 端到端集成测试 — Agent-as-Tool / ToolGroup / 完整链路验证。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError
from ckyclaw_framework.model.message import Message, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import FunctionTool, function_tool
from ckyclaw_framework.tools.tool_group import ToolGroup
from ckyclaw_framework.tools.tool_registry import ToolRegistry
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import SpanStatus, SpanType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings
    from ckyclaw_framework.runner.run_context import RunContext

# ═══════════════════════════════════════════════════════════════════
# 共享基础设施
# ═══════════════════════════════════════════════════════════════════


class MockProvider(ModelProvider):
    """可编排的 Mock LLM 提供商。按顺序返回预设响应。"""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
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
        if stream:
            return self._stream_response()
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return resp

    async def _stream_response(self) -> AsyncIterator[ModelChunk]:
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        if resp.content:
            yield ModelChunk(content=resp.content)
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield ModelChunk(
                    tool_call_chunks=[
                        ToolCallChunk(index=i, id=tc.id, name=tc.name, arguments_delta=tc.arguments),
                    ],
                )
        yield ModelChunk(finish_reason="stop")


class CollectorProcessor(TraceProcessor):
    """收集所有 Trace 事件用于断言验证。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def on_trace_start(self, trace: Any) -> None:
        self.events.append(("trace_start", trace))

    async def on_span_start(self, span: Any) -> None:
        self.events.append(("span_start", span))

    async def on_span_end(self, span: Any) -> None:
        self.events.append(("span_end", span))

    async def on_trace_end(self, trace: Any) -> None:
        self.events.append(("trace_end", trace))


class RecordingApprovalHandler(ApprovalHandler):
    """记录审批请求并按预设决策自动回复。"""

    def __init__(self, decision: ApprovalDecision = ApprovalDecision.APPROVED) -> None:
        self._decision = decision
        self.requests: list[dict[str, Any]] = []

    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        self.requests.append({
            "agent_name": run_context.agent.name,
            "action_type": action_type,
            "action_detail": action_detail,
        })
        return self._decision


# ── 共享 function_tool ────────────────────────────────────────────


@function_tool()
def get_weather(city: str) -> str:
    """获取天气信息。"""
    return f"{city}天气：晴，25°C"


@function_tool()
def search_knowledge(query: str) -> str:
    """搜索知识库。"""
    return f"关于「{query}」的搜索结果：相关知识条目 3 条"


@function_tool()
def translate_text(text: str, target_lang: str) -> str:
    """翻译文本。"""
    return f"[{target_lang}] {text}"


# ═══════════════════════════════════════════════════════════════════
# Agent-as-Tool 端到端管线
# ═══════════════════════════════════════════════════════════════════


class TestE2EAgentAsTool:
    """Agent-as-Tool 在完整 Pipeline 中的端到端验证。"""

    @pytest.mark.asyncio
    async def test_manager_calls_sub_agent_tool(self) -> None:
        """Manager Agent 通过 tool_call 调用子 Agent-as-Tool，完成多轮推理。"""
        # 子 Agent 的 provider：直接返回分析结果
        sub_provider = MockProvider([
            ModelResponse(
                content="数据分析完成：Q1收入 ¥1,200万，同比增长 15%",
                token_usage=TokenUsage(20, 30, 50),
            ),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        analyst = Agent(name="analyst", description="数据分析师 Agent")
        analyst_tool = analyst.as_tool(config=sub_config)

        # Manager 的 provider：先调用 analyst tool，再根据结果最终回复
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="analyst",
                    arguments=json.dumps({"input": "分析Q1营收数据"}),
                )],
                token_usage=TokenUsage(15, 10, 25),
            ),
            ModelResponse(
                content="根据分析师报告，Q1收入 ¥1,200万，同比增长 15%，业绩表现优异。",
                token_usage=TokenUsage(20, 25, 45),
            ),
        ])

        collector = CollectorProcessor()
        config = RunConfig(
            model_provider=manager_provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        manager = Agent(
            name="manager",
            instructions="你是管理者，需要时调用分析师。",
            tools=[analyst_tool],
        )

        result = await Runner.run(manager, "帮我看看Q1业绩", config=config)

        # 验证输出
        assert "Q1" in result.output
        assert result.last_agent_name == "manager"
        assert result.turn_count == 2

        # 验证 Tracing
        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        assert SpanType.TOOL in span_types

        # 工具 span 应包含 analyst
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert any(s.name == "analyst" for s in tool_spans)

    @pytest.mark.asyncio
    async def test_agent_tool_with_own_tools(self) -> None:
        """子 Agent 自身持有工具，Manager 调用后子 Agent 内部工具链也正常运行。"""
        # 子 Agent：先调用 get_weather 工具，再回复
        sub_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="stc1", name="get_weather", arguments='{"city": "北京"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="北京天气晴，25°C，适合出行",
                token_usage=TokenUsage(10, 10, 20),
            ),
        ])
        sub_config = RunConfig(model_provider=sub_provider)

        weather_agent = Agent(
            name="weather_agent",
            description="天气查询助手",
            tools=[get_weather],
        )
        weather_tool = weather_agent.as_tool(config=sub_config)

        # Manager provider
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="weather_agent",
                    arguments=json.dumps({"input": "北京明天天气"}),
                )],
                token_usage=TokenUsage(15, 10, 25),
            ),
            ModelResponse(
                content="北京天气晴好，推荐户外活动。",
                token_usage=TokenUsage(10, 15, 25),
            ),
        ])

        config = RunConfig(model_provider=manager_provider, tracing_enabled=True)
        manager = Agent(name="planner", tools=[weather_tool])

        result = await Runner.run(manager, "北京天气怎么样?", config=config)

        assert result.output == "北京天气晴好，推荐户外活动。"
        assert result.last_agent_name == "planner"

    @pytest.mark.asyncio
    async def test_agent_tool_plus_handoff(self) -> None:
        """一个 Agent 同时拥有 agent-as-tool 和 handoff 目标。"""
        # 子 Agent（作为 tool）
        sub_provider = MockProvider([
            ModelResponse(content="检索到 5 条相关文档", token_usage=TokenUsage(5, 5, 10)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        retriever = Agent(name="retriever", description="文档检索")
        retriever_tool = retriever.as_tool(config=sub_config)

        # Handoff 目标 Agent
        specialist = Agent(name="specialist", tools=[get_weather])

        # Triage Agent：使用 retriever_tool，然后 Handoff 到 specialist
        provider = MockProvider([
            # 先调用 retriever tool
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="retriever",
                    arguments=json.dumps({"input": "查找天气API文档"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # 然后 handoff 到 specialist
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_specialist", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # specialist 调用 get_weather
            ModelResponse(
                tool_calls=[ToolCall(id="tc2", name="get_weather", arguments='{"city": "上海"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # specialist 最终回复
            ModelResponse(
                content="根据文档和实时数据，上海天气：晴，25°C",
                token_usage=TokenUsage(10, 10, 20),
            ),
        ])

        config = RunConfig(model_provider=provider, tracing_enabled=True)
        triage = Agent(
            name="triage",
            tools=[retriever_tool],
            handoffs=[specialist],
        )

        result = await Runner.run(triage, "上海天气怎么样", config=config)

        assert result.last_agent_name == "specialist"
        assert "上海" in result.output

        # Tracing 应包含 Agent / Handoff / Tool spans
        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.HANDOFF in span_types
        assert SpanType.TOOL in span_types

    @pytest.mark.asyncio
    async def test_agent_tool_with_approval(self) -> None:
        """Agent-as-Tool 的调用受审批控制。"""
        sub_provider = MockProvider([
            ModelResponse(content="子 Agent 执行结果", token_usage=TokenUsage(5, 5, 10)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        sub_agent = Agent(name="executor", description="执行器")
        executor_tool = sub_agent.as_tool(config=sub_config)

        # Manager: 调用 executor tool → 需要审批
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="executor",
                    arguments=json.dumps({"input": "执行危险操作"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="操作已完成",
                token_usage=TokenUsage(8, 5, 13),
            ),
        ])

        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        config = RunConfig(
            model_provider=manager_provider,
            approval_mode=ApprovalMode.SUGGEST,
            approval_handler=handler,
            tracing_enabled=True,
        )

        manager = Agent(name="manager", tools=[executor_tool])
        result = await Runner.run(manager, "执行操作", config=config)

        assert result.output == "操作已完成"
        # 审批应被触发
        assert len(handler.requests) == 1
        assert handler.requests[0]["action_detail"]["tool_name"] == "executor"

    @pytest.mark.asyncio
    async def test_agent_tool_streamed(self) -> None:
        """Agent-as-Tool 流式模式下也能正常工作。"""
        sub_provider = MockProvider([
            ModelResponse(content="流式子结果", token_usage=TokenUsage(5, 5, 10)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        sub_agent = Agent(name="helper", description="辅助 Agent")
        helper_tool = sub_agent.as_tool(config=sub_config)

        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="helper",
                    arguments=json.dumps({"input": "帮我做点事"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="辅助完成，结果已返回",
                token_usage=TokenUsage(8, 8, 16),
            ),
        ])

        config = RunConfig(model_provider=manager_provider, tracing_enabled=True)
        manager = Agent(name="main", tools=[helper_tool])

        final_result: RunResult | None = None
        events_collected: list[StreamEventType] = []
        async for event in Runner.run_streamed(manager, "请帮忙", config=config):
            events_collected.append(event.type)
            if event.type == StreamEventType.RUN_COMPLETE:
                final_result = event.data

        assert final_result is not None
        assert "辅助完成" in final_result.output
        assert StreamEventType.RUN_COMPLETE in events_collected

    @pytest.mark.asyncio
    async def test_agent_tool_session_isolation(self) -> None:
        """Agent-as-Tool 使用独立 Session，不污染 Manager 的 Session。"""
        backend = InMemorySessionBackend()
        session = Session(session_id="manager-session-001", backend=backend)

        sub_provider = MockProvider([
            ModelResponse(content="子 Agent 独立执行", token_usage=TokenUsage(5, 5, 10)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        sub_agent = Agent(name="isolated", description="独立子 Agent")
        sub_tool = sub_agent.as_tool(config=sub_config)

        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="isolated",
                    arguments=json.dumps({"input": "独立任务"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(content="管理流程完成", token_usage=TokenUsage(8, 5, 13)),
        ])

        config = RunConfig(model_provider=manager_provider)
        manager = Agent(name="manager", tools=[sub_tool])

        result = await Runner.run(manager, "执行独立任务", session=session, config=config)

        assert result.output == "管理流程完成"

        # Manager 的 Session 应有记录（但不应包含子 Agent 的内部对话）
        messages = await backend.load("manager-session-001")
        assert messages is not None
        # 消息中不应出现子 Agent 的 system message
        msg_contents = [m.content for m in messages if m.content]
        assert not any("独立子 Agent" in c for c in msg_contents)


# ═══════════════════════════════════════════════════════════════════
# ToolGroup 端到端管线
# ═══════════════════════════════════════════════════════════════════


class TestE2EToolGroup:
    """ToolGroup / ToolRegistry 在完整 Pipeline 中的端到端验证。"""

    @pytest.mark.asyncio
    async def test_agent_with_tool_group_tools(self) -> None:
        """Agent 使用 ToolGroup 注册的工具执行 tool_call。"""
        # 创建 ToolGroup 并注册工具
        group = ToolGroup(name="travel-tools", tools=[get_weather], description="旅行工具组")
        assert group.get_tool("get_weather") is not None

        # Agent 使用 ToolGroup 中的工具
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "成都"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="成都天气晴好，建议去春熙路",
                token_usage=TokenUsage(12, 10, 22),
            ),
        ])

        collector = CollectorProcessor()
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        agent = Agent(name="guide", tools=group.tools)
        result = await Runner.run(agent, "成都天气如何", config=config)

        assert "成都" in result.output
        # 验证 Tool span
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert any(s.name == "get_weather" for s in tool_spans)

    @pytest.mark.asyncio
    async def test_multiple_tool_groups_merged(self) -> None:
        """多个 ToolGroup 的工具合并到同一 Agent。"""
        group_a = ToolGroup(name="weather-tools", tools=[get_weather])
        group_b = ToolGroup(name="search-tools", tools=[search_knowledge])

        merged_tools = group_a.tools + group_b.tools
        assert len(merged_tools) == 2

        # Agent 依次调用两个组的工具
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "杭州"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="tc2", name="search_knowledge", arguments='{"query": "杭州美食"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="杭州晴天25°C，推荐西湖醋鱼和龙井虾仁",
                token_usage=TokenUsage(15, 12, 27),
            ),
        ])

        config = RunConfig(model_provider=provider, tracing_enabled=True)
        agent = Agent(name="travel-assistant", tools=merged_tools)

        result = await Runner.run(agent, "杭州旅行攻略", config=config)

        assert result.output is not None
        assert result.turn_count == 3

        # 两个工具都应该被调用
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        tool_names = {s.name for s in tool_spans}
        assert "get_weather" in tool_names
        assert "search_knowledge" in tool_names

    @pytest.mark.asyncio
    async def test_tool_registry_provides_tools(self) -> None:
        """ToolRegistry 管理多 ToolGroup，Agent 从 Registry 取工具。"""
        registry = ToolRegistry()
        registry.register_group(ToolGroup(name="weather", tools=[get_weather]))
        registry.register_group(ToolGroup(name="translate", tools=[translate_text]))

        # 从 registry 获取所有工具
        all_tools: list[FunctionTool] = []
        for group in registry.list_groups():
            all_tools.extend(group.tools)

        assert len(all_tools) == 2

        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="translate_text",
                    arguments=json.dumps({"text": "你好世界", "target_lang": "English"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="翻译完成: [English] 你好世界",
                token_usage=TokenUsage(8, 8, 16),
            ),
        ])

        config = RunConfig(model_provider=provider, tracing_enabled=True)
        agent = Agent(name="polyglot", tools=all_tools)

        result = await Runner.run(agent, "翻译'你好世界'到英文", config=config)

        assert result.output is not None
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert any(s.name == "translate_text" for s in tool_spans)

    @pytest.mark.asyncio
    async def test_tool_group_with_guardrail(self) -> None:
        """ToolGroup 工具 + Guardrail 共存：Guardrail 通过后工具正常调用。"""
        async def safe_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            if "危险" in input_text:
                return GuardrailResult(tripwire_triggered=True, message="检测到危险内容")
            return GuardrailResult(tripwire_triggered=False, message="安全")

        group = ToolGroup(name="safe-tools", tools=[get_weather])

        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "深圳"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(content="深圳天气晴", token_usage=TokenUsage(8, 5, 13)),
        ])

        config = RunConfig(model_provider=provider, tracing_enabled=True)
        agent = Agent(
            name="safe-bot",
            tools=group.tools,
            input_guardrails=[InputGuardrail(guardrail_function=safe_guardrail, name="safety")],
        )

        # 正常输入 → 通过 guardrail，工具执行
        result = await Runner.run(agent, "深圳天气", config=config)
        assert "深圳" in result.output

        # 危险输入 → Guardrail 拦截
        with pytest.raises(InputGuardrailTripwireError):
            provider2 = MockProvider([ModelResponse(content="不应到达")])
            config2 = RunConfig(model_provider=provider2)
            await Runner.run(agent, "危险操作请求", config=config2)


# ═══════════════════════════════════════════════════════════════════
# 综合场景 — 全能力管线
# ═══════════════════════════════════════════════════════════════════


class TestE2ECombinedPipeline:
    """综合端到端：Agent-as-Tool + ToolGroup + Handoff + Guardrail + Approval + Tracing + Session。"""

    @pytest.mark.asyncio
    async def test_full_combined_pipeline(self) -> None:
        """最完整的综合场景：所有 Phase 6.x 能力协同工作。

        流程：
        1. Guardrail 检测输入安全
        2. Triage Agent 调用 retriever (Agent-as-Tool)
        3. Triage Handoff 到 Expert Agent
        4. Expert 调用 ToolGroup 中的 get_weather（需审批）
        5. Expert 返回最终结果
        6. Tracing 捕获全链路 Spans
        7. Session 持久化会话
        """
        collector = CollectorProcessor()
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        backend = InMemorySessionBackend()

        # Guardrail
        async def safety_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            if "禁止" in input_text:
                return GuardrailResult(tripwire_triggered=True, message="包含禁止词")
            return GuardrailResult(tripwire_triggered=False, message="安全")

        # Agent-as-Tool: retriever
        retriever_provider = MockProvider([
            ModelResponse(content="检索到 3 篇相关文档", token_usage=TokenUsage(5, 8, 13)),
        ])
        retriever_config = RunConfig(model_provider=retriever_provider)
        retriever = Agent(name="retriever", description="知识检索引擎")
        retriever_tool = retriever.as_tool(config=retriever_config)

        # ToolGroup 工具
        travel_group = ToolGroup(name="travel", tools=[get_weather], description="旅行工具组")

        # Expert Agent
        expert = Agent(
            name="expert",
            tools=travel_group.tools,
            approval_mode=ApprovalMode.SUGGEST,
        )

        # Triage Agent
        triage = Agent(
            name="triage",
            tools=[retriever_tool],
            handoffs=[expert],
            input_guardrails=[
                InputGuardrail(guardrail_function=safety_guardrail, name="safety"),
            ],
        )

        # 编排 MockProvider 响应序列
        provider = MockProvider([
            # triage: 调用 retriever tool
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="retriever",
                    arguments=json.dumps({"input": "查找旅行指南"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # triage: handoff 到 expert
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # expert: 调用 get_weather（需审批）
            ModelResponse(
                tool_calls=[ToolCall(id="tc2", name="get_weather", arguments='{"city": "三亚"}')],
                token_usage=TokenUsage(12, 6, 18),
            ),
            # expert: 最终回复
            ModelResponse(
                content="根据检索资料和实时天气数据，三亚天气晴好 25°C，推荐海滩度假。",
                token_usage=TokenUsage(20, 15, 35),
            ),
        ])

        session = Session(session_id="combined-001", backend=backend)
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            approval_mode=ApprovalMode.SUGGEST,
            approval_handler=handler,
        )

        result = await Runner.run(triage, "帮我规划三亚之旅", session=session, config=config)

        # === 验证输出 ===
        assert "三亚" in result.output
        assert result.last_agent_name == "expert"

        # === 验证 Handoff ===
        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.HANDOFF in span_types

        # === 验证 Tool（retriever + get_weather）===
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        tool_names = {s.name for s in tool_spans}
        assert "retriever" in tool_names
        assert "get_weather" in tool_names

        # === 验证 Guardrail ===
        assert SpanType.GUARDRAIL in span_types

        # === 验证审批 ===
        # 审批请求应该包含 get_weather 的调用
        weather_approvals = [r for r in handler.requests if r["action_detail"].get("tool_name") == "get_weather"]
        assert len(weather_approvals) >= 1

        # === 验证 Tracing 完整性 ===
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        for span in result.trace.spans:
            assert span.status == SpanStatus.COMPLETED

        # token_usage 记录
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        total_tokens = sum(s.token_usage["total_tokens"] for s in llm_spans)
        assert total_tokens > 0

        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"

        # === 验证 Session 持久化 ===
        messages = await backend.load("combined-001")
        assert messages is not None
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_combined_pipeline_guardrail_blocks(self) -> None:
        """综合管线中 Guardrail 拦截时，Agent-as-Tool / Handoff / Tool 均不执行。"""
        collector = CollectorProcessor()

        async def strict_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="全面拦截")

        sub_provider = MockProvider([ModelResponse(content="不应到达")])
        sub_config = RunConfig(model_provider=sub_provider)
        sub_agent = Agent(name="sub", description="不应执行的子 Agent")
        sub_tool = sub_agent.as_tool(config=sub_config)

        expert = Agent(name="expert", tools=[get_weather])
        triage = Agent(
            name="triage",
            tools=[sub_tool],
            handoffs=[expert],
            input_guardrails=[
                InputGuardrail(guardrail_function=strict_guardrail, name="blocker"),
            ],
        )

        provider = MockProvider([ModelResponse(content="不应到达")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        with pytest.raises(InputGuardrailTripwireError):
            await Runner.run(triage, "任何输入", config=config)

        # 不应有 LLM / TOOL / HANDOFF span
        span_events = [
            e[1] for e in collector.events
            if e[0] in ("span_start", "span_end") and hasattr(e[1], "type")
        ]
        for s in span_events:
            assert s.type != SpanType.LLM
            assert s.type != SpanType.HANDOFF

    @pytest.mark.asyncio
    async def test_combined_pipeline_streamed(self) -> None:
        """综合管线流式模式：Agent-as-Tool + Handoff + Tool + Tracing。"""
        # 子 Agent
        sub_provider = MockProvider([
            ModelResponse(content="流式子结果: 5条数据", token_usage=TokenUsage(5, 5, 10)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        searcher = Agent(name="searcher", description="搜索引擎")
        searcher_tool = searcher.as_tool(config=sub_config)

        # Expert
        expert = Agent(name="expert", tools=[get_weather])

        # Triage with searcher_tool + handoff to expert
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="searcher",
                    arguments=json.dumps({"input": "搜索旅行信息"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="tc2", name="get_weather", arguments='{"city": "重庆"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="重庆天气热辣，推荐火锅",
                token_usage=TokenUsage(10, 10, 20),
            ),
        ])

        collector = CollectorProcessor()
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        triage = Agent(
            name="triage",
            tools=[searcher_tool],
            handoffs=[expert],
        )

        final_result: RunResult | None = None
        event_types_collected: list[StreamEventType] = []
        async for event in Runner.run_streamed(triage, "重庆旅行攻略", config=config):
            event_types_collected.append(event.type)
            if event.type == StreamEventType.RUN_COMPLETE:
                final_result = event.data

        # 验证完成
        assert final_result is not None
        assert "重庆" in final_result.output
        assert final_result.last_agent_name == "expert"
        assert StreamEventType.RUN_COMPLETE in event_types_collected

        # Tracing
        assert final_result.trace is not None
        span_types = {s.type for s in final_result.trace.spans}
        assert SpanType.HANDOFF in span_types
        assert SpanType.TOOL in span_types

    @pytest.mark.asyncio
    async def test_multi_agent_tool_parallel_like(self) -> None:
        """Manager 拥有多个 Agent-as-Tool，依次调用。"""
        # Agent A
        provider_a = MockProvider([
            ModelResponse(content="Agent A 结果: 数据清洗完成", token_usage=TokenUsage(5, 5, 10)),
        ])
        config_a = RunConfig(model_provider=provider_a)
        agent_a = Agent(name="cleaner", description="数据清洗")
        tool_a = agent_a.as_tool(config=config_a)

        # Agent B
        provider_b = MockProvider([
            ModelResponse(content="Agent B 结果: 数据分析完成", token_usage=TokenUsage(5, 5, 10)),
        ])
        config_b = RunConfig(model_provider=provider_b)
        agent_b = Agent(name="analyzer", description="数据分析")
        tool_b = agent_b.as_tool(config=config_b)

        # Manager: 先调用 cleaner，再调用 analyzer
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="cleaner",
                    arguments=json.dumps({"input": "清洗用户数据"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc2",
                    name="analyzer",
                    arguments=json.dumps({"input": "分析清洗后的数据"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="数据处理完成：先清洗再分析，结果已就绪。",
                token_usage=TokenUsage(12, 10, 22),
            ),
        ])

        collector = CollectorProcessor()
        config = RunConfig(
            model_provider=manager_provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        manager = Agent(name="orchestrator", tools=[tool_a, tool_b])

        result = await Runner.run(manager, "处理用户数据", config=config)

        assert "数据处理完成" in result.output
        assert result.turn_count == 3

        # 两个 Agent-as-Tool 都应被调用
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        tool_names = {s.name for s in tool_spans}
        assert "cleaner" in tool_names
        assert "analyzer" in tool_names

    @pytest.mark.asyncio
    async def test_token_usage_aggregation_across_agents(self) -> None:
        """Token usage 在 Agent-as-Tool 链路中正确聚合。"""
        # 子 Agent
        sub_provider = MockProvider([
            ModelResponse(content="子结果", token_usage=TokenUsage(20, 30, 50)),
        ])
        sub_config = RunConfig(model_provider=sub_provider)
        sub_agent = Agent(name="sub", description="子 Agent")
        sub_tool = sub_agent.as_tool(config=sub_config)

        # Manager
        manager_provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(
                    id="tc1",
                    name="sub",
                    arguments=json.dumps({"input": "执行任务"}),
                )],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="任务完成",
                token_usage=TokenUsage(8, 7, 15),
            ),
        ])

        config = RunConfig(model_provider=manager_provider, tracing_enabled=True)
        manager = Agent(name="main", tools=[sub_tool])

        result = await Runner.run(manager, "开始", config=config)

        assert result.output == "任务完成"

        # Manager 的 trace 应有 LLM spans 的 token_usage
        assert result.trace is not None
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        # Manager 有 2 次 LLM 调用（tool_call + final）
        assert len(llm_spans) >= 2
        manager_tokens = sum(s.token_usage["total_tokens"] for s in llm_spans)
        assert manager_tokens == 15 + 15  # 两次 Manager LLM 调用
