"""S4 Event Sourcing + Replay — Framework 测试。

覆盖 EventJournal、EventType、EventJournalProcessor、Projector 全部模块。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from kasaya.events.journal import EventEntry, InMemoryEventJournal
from kasaya.events.processor import EventJournalProcessor
from kasaya.events.projector import AuditProjector, CostProjector, MetricsProjector
from kasaya.events.types import EventType
from kasaya.model.message import Message, TokenUsage
from kasaya.model.provider import ModelChunk, ModelProvider, ModelResponse
from kasaya.tracing.span import Span, SpanStatus, SpanType
from kasaya.tracing.trace import Trace

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from kasaya.model.settings import ModelSettings

# ─────────── 辅助设施 ───────────


class StubProvider(ModelProvider):
    """可控 Mock Provider。"""

    def __init__(self, content: str = "response") -> None:
        self._content = content
        self._calls = 0

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
        self._calls += 1
        if stream:
            return self._stream_response()
        return ModelResponse(
            content=self._content,
            tool_calls=[],
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )

    async def _stream_response(self) -> AsyncIterator[ModelChunk]:
        """模拟流式响应。"""
        yield ModelChunk(content=self._content, finish_reason="stop")


def _make_trace(trace_id: str = "t1") -> Trace:
    """创建测试 Trace。"""
    t = Trace(workflow_name="test")
    t.trace_id = trace_id
    return t


def _make_span(
    span_type: SpanType = SpanType.AGENT,
    name: str = "test",
    status: SpanStatus = SpanStatus.COMPLETED,
    **kwargs: Any,
) -> Span:
    """创建测试 Span。"""
    s = Span(
        type=span_type,
        name=name,
        status=status,
        **kwargs,
    )
    s.trace_id = "t1"
    return s


# ─────────── EventType 测试 ───────────


class TestEventType:
    """事件类型枚举测试。"""

    def test_all_types_string(self) -> None:
        """所有 EventType 值都是字符串。"""
        for et in EventType:
            assert isinstance(et.value, str)

    def test_required_types_exist(self) -> None:
        """必须的事件类型存在。"""
        required = [
            "run_start", "run_end", "agent_start", "agent_end",
            "llm_call_start", "llm_call_end", "tool_call_start", "tool_call_end",
            "handoff", "guardrail_check_start", "guardrail_check_end",
            "guardrail_tripwire", "error",
        ]
        values = {et.value for et in EventType}
        for r in required:
            assert r in values, f"Missing EventType: {r}"


# ─────────── EventEntry 测试 ───────────


class TestEventEntry:
    """EventEntry 数据类测试。"""

    def test_default_values(self) -> None:
        """默认值正确。"""
        e = EventEntry()
        assert e.event_id
        assert e.sequence == 0
        assert e.event_type == EventType.RUN_START
        assert isinstance(e.timestamp, datetime)
        assert e.payload == {}

    def test_to_dict(self) -> None:
        """to_dict 返回完整字典。"""
        e = EventEntry(
            event_type=EventType.TOOL_CALL_START,
            run_id="run-1",
            session_id="sess-1",
            agent_name="agent-a",
            span_id="span-1",
            payload={"key": "val"},
        )
        d = e.to_dict()
        assert d["event_type"] == "tool_call_start"
        assert d["run_id"] == "run-1"
        assert d["session_id"] == "sess-1"
        assert d["agent_name"] == "agent-a"
        assert d["payload"]["key"] == "val"
        assert "timestamp" in d

    def test_to_dict_payload_isolation(self) -> None:
        """to_dict 返回的 payload 是原始引用（性能优先）。"""
        payload = {"key": "val"}
        e = EventEntry(payload=payload)
        d = e.to_dict()
        assert d["payload"] is payload


# ─────────── InMemoryEventJournal 测试 ───────────


class TestInMemoryEventJournal:
    """内存事件日志测试。"""

    @pytest.mark.asyncio
    async def test_append_and_query_all(self) -> None:
        """追加事件并查询全部。"""
        j = InMemoryEventJournal()
        e1 = EventEntry(event_type=EventType.RUN_START, run_id="r1")
        e2 = EventEntry(event_type=EventType.AGENT_START, run_id="r1")
        await j.append(e1)
        await j.append(e2)
        assert j.size == 2

        events = await j.get_events()
        assert len(events) == 2
        assert events[0].sequence < events[1].sequence

    @pytest.mark.asyncio
    async def test_query_by_run_id(self) -> None:
        """按 run_id 过滤。"""
        j = InMemoryEventJournal()
        await j.append(EventEntry(event_type=EventType.RUN_START, run_id="r1"))
        await j.append(EventEntry(event_type=EventType.RUN_START, run_id="r2"))

        events = await j.get_events(run_id="r1")
        assert len(events) == 1
        assert events[0].run_id == "r1"

    @pytest.mark.asyncio
    async def test_query_by_session_id(self) -> None:
        """按 session_id 过滤。"""
        j = InMemoryEventJournal()
        await j.append(EventEntry(event_type=EventType.RUN_START, session_id="s1"))
        await j.append(EventEntry(event_type=EventType.RUN_START, session_id="s2"))

        events = await j.get_events(session_id="s1")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_query_by_event_types(self) -> None:
        """按事件类型过滤。"""
        j = InMemoryEventJournal()
        await j.append(EventEntry(event_type=EventType.RUN_START, run_id="r1"))
        await j.append(EventEntry(event_type=EventType.TOOL_CALL_START, run_id="r1"))
        await j.append(EventEntry(event_type=EventType.LLM_CALL_START, run_id="r1"))

        events = await j.get_events(event_types=[EventType.TOOL_CALL_START, EventType.LLM_CALL_START])
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_query_after_sequence(self) -> None:
        """after_sequence 过滤。"""
        j = InMemoryEventJournal()
        for _ in range(5):
            await j.append(EventEntry(event_type=EventType.RUN_START))

        # 查 sequence > 3
        events = await j.get_events(after_sequence=3)
        assert len(events) == 2
        assert events[0].sequence == 4

    @pytest.mark.asyncio
    async def test_query_limit(self) -> None:
        """limit 限制返回条数。"""
        j = InMemoryEventJournal()
        for _ in range(10):
            await j.append(EventEntry(event_type=EventType.RUN_START))

        events = await j.get_events(limit=3)
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_append_batch(self) -> None:
        """批量追加。"""
        j = InMemoryEventJournal()
        entries = [EventEntry(event_type=EventType.RUN_START) for _ in range(5)]
        await j.append_batch(entries)
        assert j.size == 5

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """清空日志。"""
        j = InMemoryEventJournal()
        await j.append(EventEntry(event_type=EventType.RUN_START))
        assert j.size == 1
        j.clear()
        assert j.size == 0

    @pytest.mark.asyncio
    async def test_sequence_monotonic(self) -> None:
        """序列号单调递增。"""
        j = InMemoryEventJournal()
        for _ in range(20):
            await j.append(EventEntry())

        events = await j.get_events()
        seqs = [e.sequence for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 20  # 无重复

    @pytest.mark.asyncio
    async def test_combined_filters(self) -> None:
        """组合过滤条件。"""
        j = InMemoryEventJournal()
        await j.append(EventEntry(event_type=EventType.RUN_START, run_id="r1", session_id="s1"))
        await j.append(EventEntry(event_type=EventType.TOOL_CALL_START, run_id="r1", session_id="s1"))
        await j.append(EventEntry(event_type=EventType.TOOL_CALL_START, run_id="r2", session_id="s1"))

        events = await j.get_events(
            run_id="r1",
            event_types=[EventType.TOOL_CALL_START],
        )
        assert len(events) == 1
        assert events[0].event_type == EventType.TOOL_CALL_START


# ─────────── EventJournalProcessor 测试 ───────────


class TestEventJournalProcessor:
    """事件日志处理器测试。"""

    @pytest.mark.asyncio
    async def test_trace_start_emits_run_start(self) -> None:
        """on_trace_start 产出 RUN_START 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1", session_id="s1")

        trace = _make_trace()
        await p.on_trace_start(trace)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.RUN_START
        assert events[0].run_id == "r1"
        assert events[0].session_id == "s1"
        assert events[0].payload["trace_id"] == "t1"

    @pytest.mark.asyncio
    async def test_trace_end_emits_run_end(self) -> None:
        """on_trace_end 产出 RUN_END 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        trace = _make_trace()
        trace.end_time = datetime.now(UTC)
        await p.on_trace_end(trace)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.RUN_END
        assert "duration_ms" in events[0].payload

    @pytest.mark.asyncio
    async def test_span_start_agent(self) -> None:
        """Agent span start → AGENT_START 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.AGENT, "my-agent", SpanStatus.RUNNING)
        await p.on_span_start(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_START
        assert events[0].agent_name == "my-agent"

    @pytest.mark.asyncio
    async def test_span_start_llm(self) -> None:
        """LLM span start → LLM_CALL_START 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.LLM, "gpt-4o", SpanStatus.RUNNING)
        await p.on_span_start(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.LLM_CALL_START

    @pytest.mark.asyncio
    async def test_span_start_tool(self) -> None:
        """Tool span start → TOOL_CALL_START 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.TOOL, "web_search", SpanStatus.RUNNING)
        await p.on_span_start(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.TOOL_CALL_START

    @pytest.mark.asyncio
    async def test_span_start_handoff(self) -> None:
        """Handoff span start → HANDOFF 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.HANDOFF, "handoff-a-b", SpanStatus.RUNNING)
        await p.on_span_start(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.HANDOFF

    @pytest.mark.asyncio
    async def test_span_end_llm_with_usage(self) -> None:
        """LLM span end 包含 token_usage。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.LLM, "gpt-4o", SpanStatus.COMPLETED)
        span.token_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        span.model = "gpt-4o"
        span.end_time = datetime.now(UTC)
        await p.on_span_end(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.LLM_CALL_END
        assert events[0].payload["token_usage"]["prompt_tokens"] == 100
        assert events[0].payload["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_span_end_tool_with_output(self) -> None:
        """Tool span end 包含 output。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.TOOL, "calc", SpanStatus.COMPLETED)
        span.output = "42"
        span.end_time = datetime.now(UTC)
        await p.on_span_end(span)

        events = await j.get_events()
        assert len(events) == 1
        assert events[0].payload["output"] == "42"

    @pytest.mark.asyncio
    async def test_span_end_error_emits_error_event(self) -> None:
        """失败的 span 额外产出 ERROR 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.TOOL, "broken_tool", SpanStatus.FAILED)
        span.output = "Connection timeout"
        span.end_time = datetime.now(UTC)
        await p.on_span_end(span)

        events = await j.get_events()
        types = [e.event_type for e in events]
        assert EventType.ERROR in types
        assert EventType.TOOL_CALL_END in types

    @pytest.mark.asyncio
    async def test_guardrail_tripwire_event(self) -> None:
        """Guardrail 失败 → GUARDRAIL_TRIPWIRE 事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.GUARDRAIL, "safety-check", SpanStatus.FAILED)
        span.output = "Blocked: unsafe content"
        span.end_time = datetime.now(UTC)
        await p.on_span_end(span)

        events = await j.get_events()
        types = [e.event_type for e in events]
        assert EventType.GUARDRAIL_TRIPWIRE in types
        assert EventType.GUARDRAIL_CHECK_END in types
        # Guardrail 失败不产出通用 ERROR（专用 TRIPWIRE 即可）
        assert EventType.ERROR not in types

    @pytest.mark.asyncio
    async def test_unknown_span_type_ignored(self) -> None:
        """未映射的 SpanType 不产出事件。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        span = _make_span(SpanType.WORKFLOW_STEP, "step-1", SpanStatus.RUNNING)
        await p.on_span_start(span)

        events = await j.get_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """完整的 trace → span → span_end → trace_end 生命周期。"""
        j = InMemoryEventJournal()
        p = EventJournalProcessor(j, run_id="r1")

        trace = _make_trace()
        await p.on_trace_start(trace)

        agent_span = _make_span(SpanType.AGENT, "main-agent", SpanStatus.RUNNING)
        await p.on_span_start(agent_span)

        llm_span = _make_span(SpanType.LLM, "gpt-4o", SpanStatus.RUNNING)
        await p.on_span_start(llm_span)

        llm_span.status = SpanStatus.COMPLETED
        llm_span.end_time = datetime.now(UTC)
        llm_span.token_usage = {"prompt_tokens": 50, "completion_tokens": 20}
        llm_span.model = "gpt-4o"
        await p.on_span_end(llm_span)

        agent_span.status = SpanStatus.COMPLETED
        agent_span.end_time = datetime.now(UTC)
        await p.on_span_end(agent_span)

        trace.end_time = datetime.now(UTC)
        await p.on_trace_end(trace)

        events = await j.get_events()
        types = [e.event_type for e in events]
        assert types == [
            EventType.RUN_START,
            EventType.AGENT_START,
            EventType.LLM_CALL_START,
            EventType.LLM_CALL_END,
            EventType.AGENT_END,
            EventType.RUN_END,
        ]

    @pytest.mark.asyncio
    async def test_projector_receives_events(self) -> None:
        """Projector 收到所有事件。"""
        j = InMemoryEventJournal()
        cost = CostProjector()
        p = EventJournalProcessor(j, run_id="r1", projectors=[cost])

        trace = _make_trace()
        await p.on_trace_start(trace)

        llm_span = _make_span(SpanType.LLM, "gpt-4o", SpanStatus.COMPLETED)
        llm_span.token_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        llm_span.model = "gpt-4o"
        llm_span.end_time = datetime.now(UTC)
        await p.on_span_end(llm_span)

        state = cost.get_state()
        assert state["total_prompt_tokens"] == 100
        assert state["total_completion_tokens"] == 50

    @pytest.mark.asyncio
    async def test_journal_error_does_not_crash(self) -> None:
        """Journal append 失败不导致 Processor 崩溃。"""
        j = InMemoryEventJournal()
        j._append = AsyncMock(side_effect=RuntimeError("disk full"))
        p = EventJournalProcessor(j, run_id="r1")

        trace = _make_trace()
        # 不应抛出异常
        await p.on_trace_start(trace)


# ─────────── CostProjector 测试 ───────────


class TestCostProjector:
    """Token 成本投射器测试。"""

    @pytest.mark.asyncio
    async def test_aggregates_llm_calls(self) -> None:
        """聚合多条 LLM 调用的 Token。"""
        proj = CostProjector()

        for _i in range(3):
            await proj.on_event(EventEntry(
                event_type=EventType.LLM_CALL_END,
                payload={
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "model": "gpt-4o",
                },
            ))

        state = proj.get_state()
        assert state["total_prompt_tokens"] == 30
        assert state["total_completion_tokens"] == 15
        assert state["total_calls"] == 3
        assert state["by_model"]["gpt-4o"]["calls"] == 3

    @pytest.mark.asyncio
    async def test_ignores_non_llm_events(self) -> None:
        """非 LLM 事件被忽略。"""
        proj = CostProjector()
        await proj.on_event(EventEntry(event_type=EventType.TOOL_CALL_START))
        assert proj.get_state()["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_multiple_models(self) -> None:
        """多模型分别统计。"""
        proj = CostProjector()
        await proj.on_event(EventEntry(
            event_type=EventType.LLM_CALL_END,
            payload={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}, "model": "gpt-4o"},
        ))
        await proj.on_event(EventEntry(
            event_type=EventType.LLM_CALL_END,
            payload={"token_usage": {"prompt_tokens": 20, "completion_tokens": 10}, "model": "deepseek"},
        ))

        state = proj.get_state()
        assert state["by_model"]["gpt-4o"]["prompt"] == 10
        assert state["by_model"]["deepseek"]["prompt"] == 20

    def test_reset(self) -> None:
        """重置后状态清零。"""
        proj = CostProjector()
        proj._state.total_calls = 5
        proj.reset()
        assert proj.get_state()["total_calls"] == 0


# ─────────── AuditProjector 测试 ───────────


class TestAuditProjector:
    """审计投射器测试。"""

    @pytest.mark.asyncio
    async def test_records_all_events(self) -> None:
        """记录所有事件摘要。"""
        proj = AuditProjector()
        await proj.on_event(EventEntry(event_type=EventType.RUN_START, run_id="r1"))
        await proj.on_event(EventEntry(event_type=EventType.ERROR, payload={"error": "fail"}))

        state = proj.get_state()
        assert state["total_events"] == 2
        # ERROR 事件有 detail
        assert state["entries"][1]["detail"] == "fail"

    @pytest.mark.asyncio
    async def test_max_entries_limit(self) -> None:
        """超过上限自动淘汰。"""
        proj = AuditProjector(max_entries=5)
        for i in range(10):
            await proj.on_event(EventEntry(event_type=EventType.RUN_START, run_id=f"r{i}"))

        state = proj.get_state()
        assert state["total_events"] == 5

    def test_reset(self) -> None:
        """重置后状态清空。"""
        proj = AuditProjector()
        proj._entries.append({"test": True})
        proj.reset()
        assert proj.get_state()["total_events"] == 0


# ─────────── MetricsProjector 测试 ───────────


class TestMetricsProjector:
    """指标投射器测试。"""

    @pytest.mark.asyncio
    async def test_counts_events(self) -> None:
        """事件计数。"""
        proj = MetricsProjector()
        await proj.on_event(EventEntry(event_type=EventType.TOOL_CALL_START))
        await proj.on_event(EventEntry(event_type=EventType.TOOL_CALL_START))
        await proj.on_event(EventEntry(event_type=EventType.LLM_CALL_START))

        state = proj.get_state()
        assert state["event_counts"]["tool_call_start"] == 2
        assert state["event_counts"]["llm_call_start"] == 1

    @pytest.mark.asyncio
    async def test_tool_duration_stats(self) -> None:
        """工具耗时统计。"""
        proj = MetricsProjector()
        await proj.on_event(EventEntry(
            event_type=EventType.TOOL_CALL_END,
            payload={"duration_ms": 100, "span_name": "calc"},
        ))
        await proj.on_event(EventEntry(
            event_type=EventType.TOOL_CALL_END,
            payload={"duration_ms": 200, "span_name": "calc"},
        ))

        state = proj.get_state()
        assert state["tool_stats"]["calc"]["count"] == 2
        assert state["tool_stats"]["calc"]["avg_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_error_and_tripwire_counts(self) -> None:
        """错误和 tripwire 计数。"""
        proj = MetricsProjector()
        await proj.on_event(EventEntry(event_type=EventType.ERROR))
        await proj.on_event(EventEntry(event_type=EventType.GUARDRAIL_TRIPWIRE))
        await proj.on_event(EventEntry(event_type=EventType.GUARDRAIL_TRIPWIRE))

        state = proj.get_state()
        assert state["error_count"] == 1
        assert state["guardrail_tripwires"] == 2

    def test_reset(self) -> None:
        """重置后状态清空。"""
        proj = MetricsProjector()
        proj._error_count = 5
        proj.reset()
        assert proj.get_state()["error_count"] == 0


# ─────────── RunConfig 集成测试 ───────────


class TestRunConfigS4Fields:
    """RunConfig S4 字段测试。"""

    def test_event_journal_default_none(self) -> None:
        """默认 event_journal 为 None。"""
        from kasaya.runner.run_config import RunConfig
        rc = RunConfig()
        assert rc.event_journal is None

    def test_event_journal_accepts_journal(self) -> None:
        """可以设置 event_journal。"""
        from kasaya.runner.run_config import RunConfig
        j = InMemoryEventJournal()
        rc = RunConfig(event_journal=j)
        assert rc.event_journal is j


# ─────────── Runner 端到端集成测试 ───────────


class TestRunnerEventJournalIntegration:
    """Runner + EventJournal 端到端测试。"""

    @pytest.mark.asyncio
    async def test_run_populates_journal(self) -> None:
        """Runner.run() 自动将事件写入 EventJournal。"""
        from kasaya.agent.agent import Agent
        from kasaya.runner.run_config import RunConfig
        from kasaya.runner.runner import Runner

        journal = InMemoryEventJournal()
        provider = StubProvider("done")

        agent = Agent(name="test-agent", instructions="be helpful")
        config = RunConfig(
            model="gpt-4o-mini",
            model_provider=provider,
            event_journal=journal,
        )

        result = await Runner.run(agent=agent, input="hello", config=config)
        assert result is not None

        events = await journal.get_events()
        types = [e.event_type for e in events]

        # 至少包含 RUN_START 和 RUN_END
        assert EventType.RUN_START in types
        assert EventType.RUN_END in types

        # 包含 AGENT_START 和 LLM 调用
        assert EventType.AGENT_START in types
        assert EventType.LLM_CALL_START in types

    @pytest.mark.asyncio
    async def test_streamed_run_populates_journal(self) -> None:
        """Runner.run_streamed() 自动将事件写入 EventJournal。"""
        from kasaya.agent.agent import Agent
        from kasaya.runner.run_config import RunConfig
        from kasaya.runner.runner import Runner

        journal = InMemoryEventJournal()
        provider = StubProvider("streamed-done")

        agent = Agent(name="stream-agent", instructions="stream")
        config = RunConfig(
            model="gpt-4o-mini",
            model_provider=provider,
            event_journal=journal,
        )

        events_collected = []
        async for event in Runner.run_streamed(agent=agent, input="hello", config=config):
            events_collected.append(event)

        journal_events = await journal.get_events()
        types = [e.event_type for e in journal_events]

        assert EventType.RUN_START in types
        assert EventType.RUN_END in types

    @pytest.mark.asyncio
    async def test_journal_events_have_run_id(self) -> None:
        """Journal 中所有事件的 run_id 一致。"""
        from kasaya.agent.agent import Agent
        from kasaya.runner.run_config import RunConfig
        from kasaya.runner.runner import Runner

        journal = InMemoryEventJournal()
        provider = StubProvider("ok")

        agent = Agent(name="rid-test", instructions="test")
        config = RunConfig(model_provider=provider, event_journal=journal)

        await Runner.run(agent=agent, input="hi", config=config)

        events = await journal.get_events()
        run_ids = {e.run_id for e in events}
        assert len(run_ids) == 1  # 所有事件共享同一个 run_id
        assert "" not in run_ids  # run_id 不为空

    @pytest.mark.asyncio
    async def test_disabled_tracing_no_events(self) -> None:
        """tracing_enabled=False 时不产出事件。"""
        from kasaya.agent.agent import Agent
        from kasaya.runner.run_config import RunConfig
        from kasaya.runner.runner import Runner

        journal = InMemoryEventJournal()
        provider = StubProvider("ok")

        agent = Agent(name="no-trace", instructions="test")
        config = RunConfig(
            model_provider=provider,
            event_journal=journal,
            tracing_enabled=False,
        )

        await Runner.run(agent=agent, input="hi", config=config)
        assert journal.size == 0
