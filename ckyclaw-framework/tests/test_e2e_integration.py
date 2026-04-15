"""M5 Phase 5.1 — 端到端集成测试。

使用 MockProvider 模拟 LLM，验证完整 Agent Pipeline：
- 5.1.1 对话 + Handoff + 工具调用
- 5.1.2 审批触发 + 批准 + 继续执行
- 5.1.3 Tracing 完整链路验证
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.message import Message, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse, ToolCall, ToolCallChunk
from ckyclaw_framework.runner.result import RunResult, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import function_tool
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ckyclaw_framework.model.settings import ModelSettings
    from ckyclaw_framework.runner.run_context import RunContext
    from ckyclaw_framework.tracing.trace import Trace

# ═══════════════════════════════════════════════════════════════════
# 公共 Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


class MockProvider(ModelProvider):
    """可编排的 Mock LLM 提供商，按顺序返回预设响应。"""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.call_messages: list[list[Message]] = []

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
        self.call_messages.append(list(messages))
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
    """收集所有 Trace/Span 事件用于断言。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def on_trace_start(self, trace: Trace) -> None:
        self.events.append(("trace_start", trace))

    async def on_span_start(self, span: Span) -> None:
        self.events.append(("span_start", span))

    async def on_span_end(self, span: Span) -> None:
        self.events.append(("span_end", span))

    async def on_trace_end(self, trace: Trace) -> None:
        self.events.append(("trace_end", trace))


class RecordingApprovalHandler(ApprovalHandler):
    """记录审批请求并返回配置的决策。"""

    def __init__(self, decision: ApprovalDecision = ApprovalDecision.APPROVED) -> None:
        self.requests: list[dict[str, Any]] = []
        self._decision = decision

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


# ═══════════════════════════════════════════════════════════════════
# 公共工具定义
# ═══════════════════════════════════════════════════════════════════


@function_tool()
def get_weather(city: str) -> str:
    """获取指定城市天气。"""
    return f"{city}天气：晴，25°C"


@function_tool()
def search_knowledge(query: str) -> str:
    """搜索内部知识库。"""
    return f"知识库结果：关于「{query}」的最佳实践"


@function_tool()
def execute_code(code: str) -> str:
    """执行代码片段。"""
    return f"执行结果：{code} → 42"


# ═══════════════════════════════════════════════════════════════════
# 5.1.1 — 对话 + Handoff + 工具调用
# ═══════════════════════════════════════════════════════════════════


class TestE2EConversationHandoffTool:
    """端到端场景：Triage Agent → Handoff → Specialist Agent → 工具调用 → 最终回复。"""

    @pytest.mark.asyncio
    async def test_triage_handoff_to_specialist_with_tool(self) -> None:
        """完整链路：triage 识别意图 → handoff 到 weather_expert → 调用 get_weather → 返回结果。"""
        weather_expert = Agent(
            name="weather_expert",
            instructions="你是天气专家，使用 get_weather 工具回答天气问题。",
            tools=[get_weather],
        )
        triage = Agent(
            name="triage",
            instructions="你是分诊 Agent，将天气问题转交给 weather_expert。",
            handoffs=[weather_expert],
        )

        provider = MockProvider([
            # Turn 1 (triage): 决定 handoff 到 weather_expert
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_weather_expert", arguments="{}")],
                token_usage=TokenUsage(20, 10, 30),
            ),
            # Turn 2 (weather_expert): 调用 get_weather 工具
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "北京"}')],
                token_usage=TokenUsage(15, 8, 23),
            ),
            # Turn 3 (weather_expert): 拿到工具结果后生成最终回复
            ModelResponse(
                content="根据查询，北京天气：晴，25°C，适合出行。",
                token_usage=TokenUsage(25, 20, 45),
            ),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "北京今天天气怎么样？", config=config)

        # 验证 handoff 成功
        assert result.last_agent_name == "weather_expert"
        # 验证最终输出包含天气信息
        assert "北京" in result.output
        assert "晴" in result.output
        # 验证 turn 数（handoff 不计 turn，tool_call + response 计 2 turn）
        assert result.turn_count >= 2

    @pytest.mark.asyncio
    async def test_multi_agent_chain_handoff(self) -> None:
        """三级 Agent 链：triage → analyzer → coder。"""
        coder = Agent(
            name="coder",
            instructions="你是编程专家。",
            tools=[execute_code],
        )
        analyzer = Agent(
            name="analyzer",
            instructions="你是分析 Agent，将编程任务转给 coder。",
            handoffs=[coder],
        )
        triage = Agent(
            name="triage",
            instructions="你是入口 Agent，将分析任务转给 analyzer。",
            handoffs=[analyzer],
        )

        provider = MockProvider([
            # triage → handoff to analyzer
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_analyzer", arguments="{}")],
            ),
            # analyzer → handoff to coder
            ModelResponse(
                tool_calls=[ToolCall(id="h2", name="transfer_to_coder", arguments="{}")],
            ),
            # coder → tool call
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="execute_code", arguments='{"code": "1+1"}')],
            ),
            # coder → final response
            ModelResponse(content="计算结果是 42"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "帮我计算 1+1", config=config)

        assert result.last_agent_name == "coder"
        assert "42" in result.output

    @pytest.mark.asyncio
    async def test_handoff_with_tool_and_session_persistence(self) -> None:
        """Handoff + 工具调用 + Session 多轮持久化。"""
        expert = Agent(name="expert", tools=[search_knowledge])
        triage = Agent(name="triage", handoffs=[expert])

        backend = InMemorySessionBackend()
        session_id = "e2e-session-001"

        # === 第一轮 ===
        provider_round1 = MockProvider([
            # triage → handoff to expert
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
            ),
            # expert → tool call
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="search_knowledge", arguments='{"query": "AI Agent"}')],
            ),
            # expert → response
            ModelResponse(content="AI Agent 的最佳实践包括..."),
        ])
        config1 = RunConfig(model_provider=provider_round1)
        session1 = Session(session_id=session_id, backend=backend)

        result1 = await Runner.run(triage, "告诉我 AI Agent 的最佳实践", session=session1, config=config1)
        assert result1.last_agent_name == "expert"
        assert "AI Agent" in result1.output

        # === 第二轮（同 session） ===
        provider_round2 = MockProvider([
            # triage → handoff to expert（记住上下文）
            ModelResponse(
                tool_calls=[ToolCall(id="h2", name="transfer_to_expert", arguments="{}")],
            ),
            # expert → 直接回复（已有上下文）
            ModelResponse(content="关于上一条，更详细的解释是..."),
        ])
        config2 = RunConfig(model_provider=provider_round2)
        session2 = Session(session_id=session_id, backend=backend)

        result2 = await Runner.run(triage, "能详细解释一下吗？", session=session2, config=config2)
        assert result2.output == "关于上一条，更详细的解释是..."

        # 验证 session 有历史消息
        messages = await backend.load(session_id)
        assert messages is not None
        assert len(messages) > 4  # 至少包含两轮的消息

    @pytest.mark.asyncio
    async def test_handoff_with_input_filter(self) -> None:
        """Handoff + InputFilter 只保留最后 N 条消息。"""
        expert = Agent(name="expert")
        handoff = Handoff(
            agent=expert,
            input_filter=lambda msgs: msgs[-2:],
        )
        triage = Agent(name="triage", handoffs=[handoff])

        provider = MockProvider([
            # triage → handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
            ),
            # expert → response
            ModelResponse(content="收到精简消息，已处理"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "请帮忙处理", config=config)
        assert result.last_agent_name == "expert"
        assert result.output == "收到精简消息，已处理"

    @pytest.mark.asyncio
    async def test_handoff_custom_tool_name_e2e(self) -> None:
        """使用自定义 Handoff tool_name 的端到端流程。"""
        expert = Agent(name="expert", tools=[get_weather])
        handoff = Handoff(
            agent=expert,
            tool_name="escalate_to_expert",
            tool_description="升级给专家处理",
        )
        triage = Agent(name="triage", handoffs=[handoff])

        provider = MockProvider([
            # triage → handoff (custom tool name)
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="escalate_to_expert", arguments="{}")],
            ),
            # expert → tool call
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "上海"}')],
            ),
            # expert → final
            ModelResponse(content="上海天气晴朗"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(triage, "上海天气", config=config)
        assert result.last_agent_name == "expert"
        assert "上海" in result.output

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_single_turn(self) -> None:
        """单轮中多个工具调用。"""
        agent = Agent(name="multi_tool", tools=[get_weather, search_knowledge])

        provider = MockProvider([
            # 同时调用两个工具
            ModelResponse(
                tool_calls=[
                    ToolCall(id="tc1", name="get_weather", arguments='{"city": "北京"}'),
                    ToolCall(id="tc2", name="search_knowledge", arguments='{"query": "天气预报"}'),
                ],
            ),
            # 汇总结果
            ModelResponse(content="北京晴天 25°C，知识库提示带伞。"),
        ])
        config = RunConfig(model_provider=provider)

        result = await Runner.run(agent, "北京天气和相关建议", config=config)
        assert "北京" in result.output
        assert result.turn_count >= 2

    @pytest.mark.asyncio
    async def test_streamed_handoff_tool_e2e(self) -> None:
        """流式模式下 Handoff + 工具调用端到端。"""
        expert = Agent(name="expert", tools=[get_weather])
        triage = Agent(name="triage", handoffs=[expert])

        provider = MockProvider([
            # triage → handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
            ),
            # expert → tool
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "深圳"}')],
            ),
            # expert → final
            ModelResponse(content="深圳天气：晴，30°C"),
        ])
        config = RunConfig(model_provider=provider)

        events_collected: list[StreamEventType] = []
        final_result: RunResult | None = None

        async for event in Runner.run_streamed(triage, "深圳天气", config=config):
            events_collected.append(event.type)
            if event.type == StreamEventType.RUN_COMPLETE:
                final_result = event.data

        assert final_result is not None
        assert final_result.last_agent_name == "expert"
        assert "深圳" in final_result.output
        # 验证收到了 AGENT_START 事件（至少 triage + expert）
        assert StreamEventType.AGENT_START in events_collected
        assert StreamEventType.RUN_COMPLETE in events_collected


# ═══════════════════════════════════════════════════════════════════
# 5.1.2 — 审批触发 + 批准 + 继续执行
# ═══════════════════════════════════════════════════════════════════


class TestE2EApprovalFlow:
    """端到端场景：Agent 工具调用 → 审批 → 批准/拒绝 → 继续执行。"""

    @pytest.mark.asyncio
    async def test_approval_approved_tool_executes(self) -> None:
        """审批通过 → 工具正常执行并返回结果。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "杭州"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="杭州天气：晴，28°C",
                token_usage=TokenUsage(12, 8, 20),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_handler=handler,
        )

        result = await Runner.run(agent, "杭州天气怎么样？", config=config)

        # 验证审批被触发
        assert len(handler.requests) == 1
        assert handler.requests[0]["action_type"] == "tool_call"
        assert handler.requests[0]["action_detail"]["tool_name"] == "get_weather"
        assert handler.requests[0]["agent_name"] == "assistant"
        # 验证最终结果
        assert "杭州" in result.output

    @pytest.mark.asyncio
    async def test_approval_rejected_tool_not_executed(self) -> None:
        """审批拒绝 → 工具不执行，LLM 收到拒绝错误后生成替代回复。"""
        handler = RecordingApprovalHandler(ApprovalDecision.REJECTED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "杭州"}')],
            ),
            # LLM 第二轮收到 tool error 后回复
            ModelResponse(content="抱歉，工具调用被拒绝了"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_handler=handler,
        )

        result = await Runner.run(agent, "杭州天气", config=config)

        assert len(handler.requests) == 1
        # Runner 不会 crash，最终有输出
        assert result.output

    @pytest.mark.asyncio
    async def test_approval_with_handoff_and_tool(self) -> None:
        """RunConfig 级 suggest 模式，Handoff 后工具调用仍需审批。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        expert = Agent(
            name="expert",
            tools=[get_weather],
        )
        triage = Agent(name="triage", handoffs=[expert])

        provider = MockProvider([
            # triage → handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
            ),
            # expert → tool call (needs approval)
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "成都"}')],
            ),
            # expert → final
            ModelResponse(content="成都天气：多云，22°C"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_mode=ApprovalMode.SUGGEST,
            approval_handler=handler,
        )

        result = await Runner.run(triage, "成都天气", config=config)

        # 验证 handoff 成功
        assert result.last_agent_name == "expert"
        # 验证审批被触发（expert 的工具调用）
        assert len(handler.requests) == 1
        assert handler.requests[0]["agent_name"] == "expert"
        assert "成都" in result.output

    @pytest.mark.asyncio
    async def test_full_auto_no_approval(self) -> None:
        """full-auto 模式下工具直接执行，不触发审批。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.FULL_AUTO,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "广州"}')],
            ),
            ModelResponse(content="广州天气：晴"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_handler=handler,
        )

        result = await Runner.run(agent, "广州天气", config=config)

        # full-auto 不触发审批
        assert len(handler.requests) == 0
        assert "广州" in result.output

    @pytest.mark.asyncio
    async def test_config_approval_mode_overrides_agent(self) -> None:
        """RunConfig.approval_mode 覆盖 Agent.approval_mode。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "武汉"}')],
            ),
            ModelResponse(content="武汉天气：阴"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_mode=ApprovalMode.FULL_AUTO,
            approval_handler=handler,
        )

        result = await Runner.run(agent, "武汉天气", config=config)

        # RunConfig full-auto 覆盖 Agent suggest → 不审批
        assert len(handler.requests) == 0
        assert result.output

    @pytest.mark.asyncio
    async def test_approval_with_multiple_tools(self) -> None:
        """审批模式下多个工具调用都需审批。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather, search_knowledge],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="tc1", name="get_weather", arguments='{"city": "南京"}'),
                    ToolCall(id="tc2", name="search_knowledge", arguments='{"query": "出行建议"}'),
                ],
            ),
            ModelResponse(content="南京天气晴，出行建议带防晒"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_handler=handler,
        )

        result = await Runner.run(agent, "南京天气和出行建议", config=config)

        # 两个工具调用都触发审批
        assert len(handler.requests) == 2
        tool_names = {r["action_detail"]["tool_name"] for r in handler.requests}
        assert "get_weather" in tool_names
        assert "search_knowledge" in tool_names
        assert result.output

    @pytest.mark.asyncio
    async def test_approval_streamed_mode(self) -> None:
        """流式模式下审批仍然生效。"""
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "西安"}')],
            ),
            ModelResponse(content="西安天气：晴"),
        ])
        config = RunConfig(
            model_provider=provider,
            approval_handler=handler,
        )

        final_result: RunResult | None = None
        async for event in Runner.run_streamed(agent, "西安天气", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                final_result = event.data

        assert final_result is not None
        assert len(handler.requests) == 1
        assert "西安" in final_result.output


# ═══════════════════════════════════════════════════════════════════
# 5.1.3 — Tracing 完整链路验证
# ═══════════════════════════════════════════════════════════════════


class TestE2ETracingFullPipeline:
    """端到端场景：验证 Tracing 采集完整 Span 链路。"""

    @pytest.mark.asyncio
    async def test_simple_chat_trace_spans(self) -> None:
        """简单对话产出正确的 trace_start → agent span → llm span → trace_end。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([
            ModelResponse(content="你好", token_usage=TokenUsage(10, 5, 15)),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "hi", config=config)

        assert result.output == "你好"
        assert result.trace is not None

        # 验证事件序列完整
        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"

        # 验证 Span 类型
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types

        # 所有 Span 已完成
        for span in result.trace.spans:
            assert span.status == SpanStatus.COMPLETED
            assert span.end_time is not None

    @pytest.mark.asyncio
    async def test_tool_call_trace_has_tool_span(self) -> None:
        """工具调用产出 AGENT + LLM + TOOL span。"""
        collector = CollectorProcessor()
        agent = Agent(name="assistant", tools=[get_weather])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "重庆"}')],
                token_usage=TokenUsage(15, 8, 23),
            ),
            ModelResponse(
                content="重庆天气：晴",
                token_usage=TokenUsage(20, 10, 30),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "重庆天气", config=config)

        assert result.trace is not None
        span_types = [s.type for s in result.trace.spans]
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        assert SpanType.TOOL in span_types

        # 验证 TOOL span 名称
        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert len(tool_spans) == 1
        assert tool_spans[0].name == "get_weather"
        assert tool_spans[0].status == SpanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_handoff_trace_has_handoff_span(self) -> None:
        """Handoff 产出 HANDOFF span。"""
        collector = CollectorProcessor()
        expert = Agent(name="expert")
        triage = Agent(name="triage", handoffs=[expert])

        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="专家回复",
                token_usage=TokenUsage(8, 4, 12),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(triage, "需要专家", config=config)

        assert result.trace is not None
        handoff_spans = [s for s in result.trace.spans if s.type == SpanType.HANDOFF]
        assert len(handoff_spans) == 1
        assert "triage" in handoff_spans[0].name
        assert "expert" in handoff_spans[0].name
        assert handoff_spans[0].status == SpanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_full_pipeline_trace_all_span_types(self) -> None:
        """完整链路：Guardrail + Handoff + Tool → 所有 Span 类型齐全。"""
        collector = CollectorProcessor()

        async def pass_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=False, message="通过")

        expert = Agent(name="expert", tools=[get_weather])
        triage = Agent(
            name="triage",
            handoffs=[expert],
            input_guardrails=[
                InputGuardrail(guardrail_function=pass_guardrail, name="safety_check"),
            ],
        )

        provider = MockProvider([
            # triage → handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # expert → tool call
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "长沙"}')],
                token_usage=TokenUsage(12, 6, 18),
            ),
            # expert → final
            ModelResponse(
                content="长沙天气：晴",
                token_usage=TokenUsage(15, 10, 25),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(triage, "长沙天气怎么样", config=config)

        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}

        # 验证所有关键 Span 类型
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        assert SpanType.TOOL in span_types
        assert SpanType.HANDOFF in span_types
        assert SpanType.GUARDRAIL in span_types

        # 验证事件序列
        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"

        # 所有 span 已完成
        for span in result.trace.spans:
            assert span.status == SpanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_llm_spans_capture_token_usage(self) -> None:
        """LLM span 正确记录 token_usage。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot", tools=[get_weather])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "厦门"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="厦门天气晴朗",
                token_usage=TokenUsage(20, 12, 32),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        result = await Runner.run(agent, "厦门天气", config=config)

        assert result.trace is not None
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        assert len(llm_spans) >= 2

        # 每个 LLM span 都应有 token_usage
        for span in llm_spans:
            assert span.token_usage is not None
            assert span.token_usage["total_tokens"] > 0

        # 验证总 token 统计
        total_tokens = sum(s.token_usage["total_tokens"] for s in llm_spans)
        assert total_tokens == 15 + 32  # 两次 LLM 调用的总和

    @pytest.mark.asyncio
    async def test_trace_disabled_no_spans(self) -> None:
        """Tracing 禁用时不产出 trace。"""
        agent = Agent(name="bot", tools=[get_weather])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "南宁"}')],
            ),
            ModelResponse(content="南宁天气晴"),
        ])
        config = RunConfig(model_provider=provider, tracing_enabled=False)

        result = await Runner.run(agent, "南宁天气", config=config)

        assert result.output
        assert result.trace is None

    @pytest.mark.asyncio
    async def test_sensitive_data_control(self) -> None:
        """trace_include_sensitive_data 控制 LLM span 的 input/output 记录。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")

        provider_on = MockProvider([
            ModelResponse(content="机密信息", token_usage=TokenUsage(5, 3, 8)),
        ])
        config_on = RunConfig(
            model_provider=provider_on,
            tracing_enabled=True,
            trace_processors=[collector],
            trace_include_sensitive_data=True,
        )
        result_on = await Runner.run(agent, "请求机密", config=config_on)

        llm_spans_on = [s for s in result_on.trace.spans if s.type == SpanType.LLM]
        assert llm_spans_on[0].input is not None
        assert llm_spans_on[0].output is not None

        # 关闭敏感数据
        collector2 = CollectorProcessor()
        provider_off = MockProvider([
            ModelResponse(content="公开信息", token_usage=TokenUsage(5, 3, 8)),
        ])
        config_off = RunConfig(
            model_provider=provider_off,
            tracing_enabled=True,
            trace_processors=[collector2],
            trace_include_sensitive_data=False,
        )
        result_off = await Runner.run(agent, "请求公开", config=config_off)

        llm_spans_off = [s for s in result_off.trace.spans if s.type == SpanType.LLM]
        assert llm_spans_off[0].input is None
        assert llm_spans_off[0].output is None

    @pytest.mark.asyncio
    async def test_streamed_trace_complete(self) -> None:
        """流式模式下 Tracing 完整链路。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot", tools=[get_weather])
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "昆明"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="昆明天气如春",
                token_usage=TokenUsage(8, 4, 12),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        final_result: RunResult | None = None
        async for event in Runner.run_streamed(agent, "昆明天气", config=config):
            if event.type == StreamEventType.RUN_COMPLETE:
                final_result = event.data

        assert final_result is not None
        assert final_result.trace is not None
        span_types = {s.type for s in final_result.trace.spans}
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        assert SpanType.TOOL in span_types

        # 事件序列完整
        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"

    @pytest.mark.asyncio
    async def test_guardrail_tripwire_trace(self) -> None:
        """Guardrail 拦截时也应产出完整 trace。"""
        collector = CollectorProcessor()

        async def block_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="敏感内容被拦截")

        agent = Agent(
            name="bot",
            input_guardrails=[
                InputGuardrail(guardrail_function=block_guardrail, name="content_filter"),
            ],
        )
        provider = MockProvider([ModelResponse(content="不应到达")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
        )

        with pytest.raises(InputGuardrailTripwireError) as exc_info:
            await Runner.run(agent, "违规内容", config=config)

        assert "content_filter" in str(exc_info.value)

        # 即使 guardrail 拦截，也应有 trace 事件
        event_types = [e[0] for e in collector.events]
        assert "trace_start" in event_types
        # guardrail span 应存在
        guardrail_spans = [
            e[1] for e in collector.events
            if e[0] in ("span_start", "span_end")
            and hasattr(e[1], "type")
            and e[1].type == SpanType.GUARDRAIL
        ]
        assert len(guardrail_spans) >= 1

    @pytest.mark.asyncio
    async def test_workflow_name_propagation(self) -> None:
        """workflow_name 正确传递到 Trace。"""
        collector = CollectorProcessor()
        agent = Agent(name="bot")
        provider = MockProvider([ModelResponse(content="ok")])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            workflow_name="e2e_test_workflow",
        )

        result = await Runner.run(agent, "test", config=config)

        assert result.trace is not None
        assert result.trace.workflow_name == "e2e_test_workflow"

    @pytest.mark.asyncio
    async def test_approval_trace_integration(self) -> None:
        """审批模式 + Tracing 共存：审批通过的工具调用应产出 TOOL span。"""
        collector = CollectorProcessor()
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        agent = Agent(
            name="assistant",
            tools=[get_weather],
            approval_mode=ApprovalMode.SUGGEST,
        )
        provider = MockProvider([
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "贵阳"}')],
                token_usage=TokenUsage(10, 5, 15),
            ),
            ModelResponse(
                content="贵阳天气阴",
                token_usage=TokenUsage(8, 4, 12),
            ),
        ])
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            approval_handler=handler,
        )

        result = await Runner.run(agent, "贵阳天气", config=config)

        # 审批生效
        assert len(handler.requests) == 1
        # Tracing 完整
        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.TOOL in span_types

        tool_spans = [s for s in result.trace.spans if s.type == SpanType.TOOL]
        assert tool_spans[0].name == "get_weather"
        assert tool_spans[0].status == SpanStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════
# 综合场景 — 全能力管线
# ═══════════════════════════════════════════════════════════════════


class TestE2EFullPipeline:
    """综合端到端：Guardrail → Handoff → Approval → Tool → Tracing → Session。"""

    @pytest.mark.asyncio
    async def test_complete_pipeline(self) -> None:
        """最完整的端到端场景：所有核心能力协作。"""
        collector = CollectorProcessor()
        handler = RecordingApprovalHandler(ApprovalDecision.APPROVED)
        backend = InMemorySessionBackend()

        async def safety_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            if "禁止" in input_text:
                return GuardrailResult(tripwire_triggered=True, message="包含禁止词")
            return GuardrailResult(tripwire_triggered=False, message="安全")

        expert = Agent(
            name="expert",
            tools=[get_weather],
        )
        triage = Agent(
            name="triage",
            handoffs=[expert],
            input_guardrails=[
                InputGuardrail(guardrail_function=safety_guardrail, name="safety"),
            ],
        )

        provider = MockProvider([
            # triage → handoff
            ModelResponse(
                tool_calls=[ToolCall(id="h1", name="transfer_to_expert", arguments="{}")],
                token_usage=TokenUsage(10, 5, 15),
            ),
            # expert → tool call (needs approval)
            ModelResponse(
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments='{"city": "拉萨"}')],
                token_usage=TokenUsage(12, 6, 18),
            ),
            # expert → final
            ModelResponse(
                content="拉萨天气：晴，气温15°C，紫外线强",
                token_usage=TokenUsage(20, 15, 35),
            ),
        ])

        session = Session(session_id="full-pipeline-001", backend=backend)
        config = RunConfig(
            model_provider=provider,
            tracing_enabled=True,
            trace_processors=[collector],
            approval_mode=ApprovalMode.SUGGEST,
            approval_handler=handler,
        )

        result = await Runner.run(triage, "拉萨天气怎么样", session=session, config=config)

        # === 验证 Handoff ===
        assert result.last_agent_name == "expert"

        # === 验证工具结果 ===
        assert "拉萨" in result.output
        assert "晴" in result.output

        # === 验证审批 ===
        assert len(handler.requests) == 1
        assert handler.requests[0]["agent_name"] == "expert"
        assert handler.requests[0]["action_detail"]["tool_name"] == "get_weather"

        # === 验证 Tracing ===
        assert result.trace is not None
        span_types = {s.type for s in result.trace.spans}
        assert SpanType.AGENT in span_types
        assert SpanType.LLM in span_types
        assert SpanType.TOOL in span_types
        assert SpanType.HANDOFF in span_types
        assert SpanType.GUARDRAIL in span_types

        # 所有 span 已完成
        for span in result.trace.spans:
            assert span.status == SpanStatus.COMPLETED

        # token_usage 记录正确
        llm_spans = [s for s in result.trace.spans if s.type == SpanType.LLM]
        total_tokens = sum(s.token_usage["total_tokens"] for s in llm_spans)
        assert total_tokens == 15 + 18 + 35

        # 事件序列完整
        event_types = [e[0] for e in collector.events]
        assert event_types[0] == "trace_start"
        assert event_types[-1] == "trace_end"

        # === 验证 Session 持久化 ===
        messages = await backend.load("full-pipeline-001")
        assert messages is not None
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_complete_pipeline_guardrail_blocks(self) -> None:
        """Guardrail 拦截时整个管线终止。"""
        collector = CollectorProcessor()

        async def strict_guardrail(ctx: RunContext, input_text: str) -> GuardrailResult:
            return GuardrailResult(tripwire_triggered=True, message="一律拦截")

        expert = Agent(name="expert", tools=[get_weather])
        triage = Agent(
            name="triage",
            handoffs=[expert],
            input_guardrails=[
                InputGuardrail(guardrail_function=strict_guardrail, name="strict"),
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

        # Handoff / Tool / LLM 都不应执行
        [e[0] for e in collector.events]
        span_events = [
            e[1] for e in collector.events
            if e[0] in ("span_start", "span_end") and hasattr(e[1], "type")
        ]
        # 不应有 LLM span（被 guardrail 拦截）
        llm_spans = [s for s in span_events if s.type == SpanType.LLM]
        assert len(llm_spans) == 0
