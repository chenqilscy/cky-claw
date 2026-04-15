"""微性能基准测试 — 验证核心热路径的执行效率。

覆盖场景：
1. FunctionTool.to_openai_schema() — 工具 Schema 序列化（每次 LLM 调用）
2. _build_tool_schemas() — 多工具批量构建（Agent Loop 热路径）
3. Message.to_dict() — 消息序列化（Session 存储/LLM 通信）
4. InMemorySessionBackend — 读写吞吐
5. Tracing Span/Trace 创建 — 每个操作的可观测性开销
6. RegexGuardrail.check() — 安全护栏检测性能
7. Agent 构造 + 嵌套 Handoff 解析 — 开销评估
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model.message import Message, MessageRole
from ckyclaw_framework.runner.runner import _build_tool_schemas
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace


# ═══════════════════════════════════════════════════════════════════
# 辅助工具
# ═══════════════════════════════════════════════════════════════════


def _timeit(fn: Any, iterations: int = 1000) -> dict[str, float]:
    """同步函数微基准：返回 min/max/mean/p95（微秒）。"""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        elapsed_us = (time.perf_counter_ns() - start) / 1_000
        times.append(elapsed_us)
    times.sort()
    p95_idx = int(len(times) * 0.95)
    return {
        "min_us": times[0],
        "max_us": times[-1],
        "mean_us": statistics.mean(times),
        "p95_us": times[p95_idx],
        "iterations": iterations,
    }


async def _async_timeit(fn: Any, iterations: int = 1000) -> dict[str, float]:
    """异步函数微基准：返回 min/max/mean/p95（微秒）。"""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        await fn()
        elapsed_us = (time.perf_counter_ns() - start) / 1_000
        times.append(elapsed_us)
    times.sort()
    p95_idx = int(len(times) * 0.95)
    return {
        "min_us": times[0],
        "max_us": times[-1],
        "mean_us": statistics.mean(times),
        "p95_us": times[p95_idx],
        "iterations": iterations,
    }


def _make_tool(name: str = "test_tool") -> FunctionTool:
    """创建一个测试用 FunctionTool。"""
    async def dummy_fn(query: str, limit: int = 10) -> str:
        return f"result for {query}"

    return FunctionTool(
        name=name,
        description=f"A test tool called {name}",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
        fn=dummy_fn,
    )


def _make_message(role: MessageRole = MessageRole.USER, content: str = "Hello") -> Message:
    """创建一个测试用 Message。"""
    return Message(role=role, content=content)


# ═══════════════════════════════════════════════════════════════════
# 1. FunctionTool.to_openai_schema() 序列化
# ═══════════════════════════════════════════════════════════════════


class TestToolSchemaSerialization:
    """工具 Schema 序列化基准：每次 LLM 调用都需要将工具列表转为 JSON Schema。"""

    def test_single_tool_schema_p95_under_10us(self) -> None:
        """单个工具 → OpenAI schema 序列化 p95 < 10μs。"""
        tool = _make_tool()
        result = _timeit(tool.to_openai_schema, iterations=5000)
        assert result["p95_us"] < 10, f"p95={result['p95_us']:.1f}μs 超过 10μs 阈值"

    def test_schema_output_structure(self) -> None:
        """验证 schema 输出结构正确。"""
        tool = _make_tool("search")
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "parameters" in schema["function"]


# ═══════════════════════════════════════════════════════════════════
# 2. _build_tool_schemas() — 批量构建
# ═══════════════════════════════════════════════════════════════════


class TestBuildToolSchemas:
    """多工具批量构建基准：Agent 拥有 5-20 个工具是常见场景。"""

    def test_5_tools_p95_under_50us(self) -> None:
        """5 个工具批量构建 p95 < 50μs。"""
        agent = Agent(
            name="bench_agent",
            instructions="test",
            tools=[_make_tool(f"tool_{i}") for i in range(5)],
        )
        result = _timeit(lambda: _build_tool_schemas(agent), iterations=3000)
        assert result["p95_us"] < 50, f"p95={result['p95_us']:.1f}μs 超过 50μs 阈值"

    def test_20_tools_p95_under_200us(self) -> None:
        """20 个工具批量构建 p95 < 200μs。"""
        agent = Agent(
            name="bench_agent",
            instructions="test",
            tools=[_make_tool(f"tool_{i}") for i in range(20)],
        )
        result = _timeit(lambda: _build_tool_schemas(agent), iterations=2000)
        assert result["p95_us"] < 200, f"p95={result['p95_us']:.1f}μs 超过 200μs 阈值"

    def test_with_handoffs_p95_under_100us(self) -> None:
        """5 工具 + 3 Handoff 批量构建 p95 < 100μs。"""
        sub_agents = [
            Agent(name=f"sub_{i}", instructions=f"Sub agent {i}")
            for i in range(3)
        ]
        agent = Agent(
            name="orchestrator",
            instructions="orchestrate",
            tools=[_make_tool(f"tool_{i}") for i in range(5)],
            handoffs=sub_agents,
        )
        result = _timeit(lambda: _build_tool_schemas(agent), iterations=2000)
        assert result["p95_us"] < 100, f"p95={result['p95_us']:.1f}μs 超过 100μs 阈值"


# ═══════════════════════════════════════════════════════════════════
# 3. Message 序列化
# ═══════════════════════════════════════════════════════════════════


class TestMessageSerialization:
    """消息序列化基准：Session 存储和 LLM 通信的核心。"""

    def test_simple_message_to_dict_p95_under_15us(self) -> None:
        """简单文本消息 to_dict p95 < 15μs。"""
        msg = _make_message(content="Hello, how can I help you?")
        result = _timeit(msg.to_dict, iterations=5000)
        assert result["p95_us"] < 15, f"p95={result['p95_us']:.1f}μs 超过 15μs 阈值"

    def test_tool_call_message_to_dict_p95_under_10us(self) -> None:
        """带 tool_calls 的消息 to_dict p95 < 10μs。"""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            agent_name="helper",
            tool_calls=[
                {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": '{"query":"test"}'}},
                {"id": "call_2", "type": "function", "function": {"name": "calc", "arguments": '{"expr":"1+1"}'}},
            ],
        )
        result = _timeit(msg.to_dict, iterations=3000)
        assert result["p95_us"] < 10, f"p95={result['p95_us']:.1f}μs 超过 10μs 阈值"

    def test_batch_100_messages_under_2ms(self) -> None:
        """100 条消息批量序列化 < 2ms。"""
        msgs = [_make_message(content=f"Message {i}") for i in range(100)]

        def serialize_all() -> list[dict[str, Any]]:
            return [m.to_dict() for m in msgs]

        result = _timeit(serialize_all, iterations=1000)
        assert result["p95_us"] < 2000, f"p95={result['p95_us']:.1f}μs 超过 2000μs(2ms) 阈值"


# ═══════════════════════════════════════════════════════════════════
# 4. InMemorySessionBackend 性能
# ═══════════════════════════════════════════════════════════════════


class TestSessionBackendPerformance:
    """内存 Session 后端吞吐：读写性能基准。"""

    @pytest.mark.asyncio
    async def test_write_1000_messages_under_50ms(self) -> None:
        """写入 1000 条消息到同一 session < 50ms。"""
        backend = InMemorySessionBackend()
        messages = [_make_message(content=f"msg_{i}") for i in range(1000)]

        start = time.perf_counter_ns()
        # 分 10 批写入，每批 100 条
        for batch_start in range(0, 1000, 100):
            await backend.save("bench_session", messages[batch_start:batch_start + 100])
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        assert elapsed_ms < 50, f"写入 1000 条耗时 {elapsed_ms:.1f}ms 超过 50ms 阈值"

    @pytest.mark.asyncio
    async def test_load_1000_messages_under_10ms(self) -> None:
        """读取 1000 条消息 < 10ms。"""
        backend = InMemorySessionBackend()
        messages = [_make_message(content=f"msg_{i}") for i in range(1000)]
        await backend.save("bench_session", messages)

        start = time.perf_counter_ns()
        loaded = await backend.load("bench_session")
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        assert loaded is not None
        assert len(loaded) == 1000
        assert elapsed_ms < 10, f"读取 1000 条耗时 {elapsed_ms:.1f}ms 超过 10ms 阈值"

    @pytest.mark.asyncio
    async def test_concurrent_reads_under_20ms(self) -> None:
        """10 个并发读取请求 < 20ms 完成。"""
        backend = InMemorySessionBackend()
        messages = [_make_message(content=f"msg_{i}") for i in range(500)]
        await backend.save("bench_session", messages)

        start = time.perf_counter_ns()
        tasks = [backend.load("bench_session") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        assert all(r is not None and len(r) == 500 for r in results)
        assert elapsed_ms < 20, f"10 并发读取耗时 {elapsed_ms:.1f}ms 超过 20ms 阈值"


# ═══════════════════════════════════════════════════════════════════
# 5. Tracing Span/Trace 创建开销
# ═══════════════════════════════════════════════════════════════════


class TestTracingOverhead:
    """链路追踪创建开销：不应成为性能瓶颈。"""

    def test_span_creation_p95_under_30us(self) -> None:
        """Span 实例化 p95 < 30μs。"""
        def create_span() -> Span:
            return Span(
                trace_id="trace_1",
                type=SpanType.TOOL,
                name="search_tool",
                status=SpanStatus.COMPLETED,
                input="query",
                output="result",
                metadata={"key": "value"},
            )
        result = _timeit(create_span, iterations=5000)
        assert result["p95_us"] < 30, f"p95={result['p95_us']:.1f}μs 超过 30μs 阈值"

    def test_trace_with_20_spans_p95_under_800us(self) -> None:
        """创建 Trace + 20 Span p95 < 800μs。"""
        def create_trace_with_spans() -> Trace:
            trace = Trace(workflow_name="benchmark")
            for i in range(20):
                span = Span(
                    trace_id=trace.trace_id,
                    type=SpanType.TOOL,
                    name=f"tool_{i}",
                    status=SpanStatus.COMPLETED,
                )
                trace.spans.append(span)
            return trace

        result = _timeit(create_trace_with_spans, iterations=2000)
        assert result["p95_us"] < 800, f"p95={result['p95_us']:.1f}μs 超过 800μs 阈值"

    def test_span_duration_calculation(self) -> None:
        """Span.duration_ms 属性计算无开销。"""
        from datetime import datetime, timedelta, timezone
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(milliseconds=150)
        span = Span(start_time=start, end_time=end)

        result = _timeit(lambda: span.duration_ms, iterations=5000)
        assert span.duration_ms == 150
        assert result["p95_us"] < 2, f"p95={result['p95_us']:.1f}μs 超过 2μs 阈值"


# ═══════════════════════════════════════════════════════════════════
# 6. RegexGuardrail 检测性能
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailPerformance:
    """安全护栏检测性能：每次用户输入和 Agent 输出都会执行。"""

    @pytest.mark.asyncio
    async def test_regex_5_patterns_p95_under_80us(self) -> None:
        """5 个正则模式检测 p95 < 80μs。"""
        guard = RegexGuardrail(
            patterns=[
                r"\b(?:password|secret|api_key)\b",
                r"\b\d{16}\b",  # 信用卡号
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
                r"(?:DROP|DELETE|TRUNCATE)\s+TABLE",  # SQL 注入
                r"<script[^>]*>",  # XSS
            ],
            name="security_guard",
        )
        text = "This is a normal user message asking about product pricing and features."

        result = await _async_timeit(lambda: guard.check(text), iterations=3000)
        assert result["p95_us"] < 80, f"p95={result['p95_us']:.1f}μs 超过 80μs 阈值"

    @pytest.mark.asyncio
    async def test_keyword_20_keywords_p95_under_150us(self) -> None:
        """20 个关键词检测 p95 < 150μs。"""
        guard = RegexGuardrail(
            keywords=[
                "bomb", "weapon", "hack", "crack", "exploit",
                "malware", "trojan", "phishing", "ransomware", "backdoor",
                "inject", "overflow", "bypass", "privilege", "escalation",
                "rootkit", "keylogger", "spyware", "worm", "virus",
            ],
            name="content_safety",
        )
        text = "I need help building a web application with React and FastAPI for my company."

        result = await _async_timeit(lambda: guard.check(text), iterations=3000)
        assert result["p95_us"] < 150, f"p95={result['p95_us']:.1f}μs 超过 150μs 阈值"

    @pytest.mark.asyncio
    async def test_guardrail_long_text_1k_chars_p95_under_300us(self) -> None:
        """1KB 长文本护栏检测 p95 < 300μs。"""
        guard = RegexGuardrail(
            patterns=[r"\b(?:password|secret)\b", r"<script", r"DROP TABLE"],
            name="long_text_guard",
        )
        text = "This is a normal text. " * 50  # ~1100 chars

        result = await _async_timeit(lambda: guard.check(text), iterations=2000)
        assert result["p95_us"] < 300, f"p95={result['p95_us']:.1f}μs 超过 300μs 阈值"


# ═══════════════════════════════════════════════════════════════════
# 7. Agent 构造开销
# ═══════════════════════════════════════════════════════════════════


class TestAgentConstruction:
    """Agent 实例化开销评估。"""

    def test_simple_agent_creation_p95_under_10us(self) -> None:
        """简单 Agent（无工具/Handoff）实例化 p95 < 10μs。"""
        def create_agent() -> Agent:
            return Agent(
                name="simple",
                instructions="You are a helpful assistant.",
            )
        result = _timeit(create_agent, iterations=5000)
        assert result["p95_us"] < 10, f"p95={result['p95_us']:.1f}μs 超过 10μs 阈值"

    def test_complex_agent_creation_p95_under_50us(self) -> None:
        """复杂 Agent（10 工具 + 3 Handoff）实例化 p95 < 50μs。"""
        sub_agents = [Agent(name=f"sub_{i}", instructions=f"I am sub agent {i}") for i in range(3)]
        tools = [_make_tool(f"tool_{i}") for i in range(10)]

        def create_complex_agent() -> Agent:
            return Agent(
                name="complex",
                instructions="You are a complex orchestrator.",
                tools=tools,
                handoffs=sub_agents,
            )
        result = _timeit(create_complex_agent, iterations=3000)
        assert result["p95_us"] < 50, f"p95={result['p95_us']:.1f}μs 超过 50μs 阈值"


# ═══════════════════════════════════════════════════════════════════
# 8. 综合场景 — 模拟单轮 Agent Loop 开销（不含 LLM 调用）
# ═══════════════════════════════════════════════════════════════════


class TestAgentLoopOverhead:
    """Agent Loop 非 LLM 开销评估：构建 Schema + 序列化消息 + 创建 Span。"""

    def test_single_turn_overhead_under_500us(self) -> None:
        """单轮 Agent Loop 非 LLM 开销（Schema + 消息序列化 + Span 创建）< 500μs。"""
        agent = Agent(
            name="test_agent",
            instructions="You are a helpful assistant.",
            tools=[_make_tool(f"tool_{i}") for i in range(10)],
        )
        messages = [
            _make_message(MessageRole.SYSTEM, "System prompt"),
            _make_message(MessageRole.USER, "User message"),
            _make_message(MessageRole.ASSISTANT, "Previous response"),
            _make_message(MessageRole.USER, "Follow up question"),
        ]

        def simulate_turn() -> tuple[list[dict[str, Any]], list[dict[str, Any]], Trace]:
            # 1. 构建工具 Schema
            schemas = _build_tool_schemas(agent)
            # 2. 序列化消息
            serialized = [m.to_dict() for m in messages]
            # 3. 创建 Trace + Span
            trace = Trace(workflow_name="benchmark")
            agent_span = Span(
                trace_id=trace.trace_id,
                type=SpanType.AGENT,
                name=agent.name,
                status=SpanStatus.RUNNING,
                input=serialized[-1]["content"],
            )
            llm_span = Span(
                trace_id=trace.trace_id,
                parent_span_id=agent_span.span_id,
                type=SpanType.LLM,
                name="gpt-4o",
                status=SpanStatus.RUNNING,
            )
            trace.spans.extend([agent_span, llm_span])
            return schemas, serialized, trace

        result = _timeit(simulate_turn, iterations=2000)
        assert result["p95_us"] < 500, f"p95={result['p95_us']:.1f}μs 超过 500μs 阈值"

    @pytest.mark.asyncio
    async def test_session_round_trip_under_1ms(self) -> None:
        """Session 写入 5 条消息 + 读取全部 < 1ms。"""
        backend = InMemorySessionBackend()
        messages = [_make_message(content=f"turn_{i}") for i in range(5)]

        async def round_trip() -> list[Message] | None:
            await backend.save("bench", messages)
            return await backend.load("bench")

        result = await _async_timeit(round_trip, iterations=1000)
        assert result["p95_us"] < 1000, f"p95={result['p95_us']:.1f}μs 超过 1000μs(1ms) 阈值"
