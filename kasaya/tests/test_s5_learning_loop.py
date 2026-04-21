"""S5 LearningLoop — 运行反思 → 信号采集 → 建议生成 测试。"""

from __future__ import annotations

import pytest

from kasaya.evolution.config import EvolutionConfig
from kasaya.evolution.learning_loop import (
    LearningLoop,
    RunReflection,
    RunReflector,
)
from kasaya.evolution.proposal import ProposalType
from kasaya.evolution.signals import (
    MetricSignal,
    SignalCollector,
    SignalType,
)
from kasaya.evolution.strategy import StrategyEngine

# ── helper ─────────────────────────────────────────────────


def _make_trace(
    *,
    trace_id: str = "t-001",
    agent_name: str = "bot",
    status: str = "ok",
    duration_ms: int = 500,
    spans: list[dict] | None = None,
) -> dict:
    """构造最小 trace_data 字典。"""
    return {
        "trace_id": trace_id,
        "agent_name": agent_name,
        "status": status,
        "duration_ms": duration_ms,
        "spans": spans or [],
    }


def _llm_span(tokens: int = 100, status: str = "ok") -> dict:
    return {"type": "llm", "status": status, "token_usage": {"total_tokens": tokens}}


def _tool_span(status: str = "ok") -> dict:
    return {"type": "tool", "status": status}


def _guardrail_span(status: str = "ok") -> dict:
    return {"type": "guardrail", "status": status}


# ══════════════════════════════════════════════════════════════
# RunReflection
# ══════════════════════════════════════════════════════════════


class TestRunReflection:
    """RunReflection 数据类测试。"""

    def test_defaults(self) -> None:
        """默认值正确。"""
        r = RunReflection()
        assert r.run_id == ""
        assert r.agent_name == ""
        assert r.success is True
        assert r.turn_count == 0
        assert r.tool_calls == 0
        assert r.tool_failures == 0
        assert r.guardrail_trips == 0
        assert r.total_tokens == 0
        assert r.duration_ms == 0
        assert r.error_message == ""
        assert r.scores == {}

    def test_custom_values(self) -> None:
        """可以设置自定义值。"""
        r = RunReflection(
            run_id="r-1",
            agent_name="my-bot",
            success=False,
            turn_count=5,
            tool_calls=10,
            tool_failures=2,
            guardrail_trips=1,
            total_tokens=3000,
            duration_ms=1200,
            error_message="timeout",
            scores={"accuracy": 0.8},
        )
        assert r.run_id == "r-1"
        assert r.agent_name == "my-bot"
        assert r.success is False
        assert r.turn_count == 5
        assert r.tool_calls == 10
        assert r.tool_failures == 2
        assert r.guardrail_trips == 1
        assert r.total_tokens == 3000
        assert r.duration_ms == 1200
        assert r.error_message == "timeout"
        assert r.scores == {"accuracy": 0.8}


# ══════════════════════════════════════════════════════════════
# RunReflector
# ══════════════════════════════════════════════════════════════


class TestRunReflector:
    """RunReflector 从 trace 数据提取反思。"""

    def test_empty_trace(self) -> None:
        """空 trace 产生空反思。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[]))
        assert r.success is True
        assert r.turn_count == 0
        assert r.tool_calls == 0
        assert r.tool_failures == 0
        assert r.guardrail_trips == 0
        assert r.total_tokens == 0

    def test_counts_llm_spans(self) -> None:
        """正确统计 LLM 轮次和 Token。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[
            _llm_span(tokens=100),
            _llm_span(tokens=200),
            _llm_span(tokens=300),
        ]))
        assert r.turn_count == 3
        assert r.total_tokens == 600

    def test_counts_tool_spans(self) -> None:
        """正确统计工具调用和失败。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[
            _tool_span(status="ok"),
            _tool_span(status="ok"),
            _tool_span(status="failed"),
        ]))
        assert r.tool_calls == 3
        assert r.tool_failures == 1

    def test_counts_guardrail_trips(self) -> None:
        """正确统计护栏触发。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[
            _guardrail_span(status="ok"),
            _guardrail_span(status="failed"),
            _guardrail_span(status="failed"),
        ]))
        assert r.guardrail_trips == 2

    def test_failed_status(self) -> None:
        """trace status=failed → success=False。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(status="failed"))
        assert r.success is False

    def test_basic_metadata(self) -> None:
        """run_id / agent_name / duration_ms 正确传递。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(
            trace_id="t-42",
            agent_name="alpha",
            duration_ms=999,
        ))
        assert r.run_id == "t-42"
        assert r.agent_name == "alpha"
        assert r.duration_ms == 999

    def test_mixed_spans(self) -> None:
        """混合 span 类型正确分类。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[
            _llm_span(tokens=50),
            _tool_span(status="ok"),
            _tool_span(status="failed"),
            _guardrail_span(status="failed"),
            _llm_span(tokens=80),
            _tool_span(status="ok"),
        ]))
        assert r.turn_count == 2
        assert r.total_tokens == 130
        assert r.tool_calls == 3
        assert r.tool_failures == 1
        assert r.guardrail_trips == 1

    def test_llm_span_without_token_usage(self) -> None:
        """LLM span 缺少 token_usage 时不崩溃。"""
        reflector = RunReflector()
        r = reflector.reflect(_make_trace(spans=[
            {"type": "llm", "status": "ok"},
        ]))
        assert r.turn_count == 1
        assert r.total_tokens == 0


# ══════════════════════════════════════════════════════════════
# RunReflector._compute_scores
# ══════════════════════════════════════════════════════════════


class TestRunReflectorScores:
    """_compute_scores 评分逻辑测试。"""

    def _score(self, **kwargs: object) -> dict[str, float]:
        """快捷工具：构造 RunReflection 并计算分数。"""
        r = RunReflection(**kwargs)  # type: ignore[arg-type]
        return RunReflector()._compute_scores(r)

    # ── accuracy ─────────────────────────────────────────

    def test_accuracy_success(self) -> None:
        assert self._score(success=True)["accuracy"] == 1.0

    def test_accuracy_failure(self) -> None:
        assert self._score(success=False)["accuracy"] == 0.0

    # ── efficiency ───────────────────────────────────────

    def test_efficiency_low_turns(self) -> None:
        assert self._score(turn_count=1)["efficiency"] == 1.0
        assert self._score(turn_count=3)["efficiency"] == 1.0

    def test_efficiency_medium_turns(self) -> None:
        assert self._score(turn_count=4)["efficiency"] == 0.7
        assert self._score(turn_count=6)["efficiency"] == 0.7

    def test_efficiency_high_turns(self) -> None:
        assert self._score(turn_count=7)["efficiency"] == 0.5
        assert self._score(turn_count=10)["efficiency"] == 0.5

    def test_efficiency_very_high_turns(self) -> None:
        assert self._score(turn_count=11)["efficiency"] == 0.3
        assert self._score(turn_count=100)["efficiency"] == 0.3

    # ── tool_usage ───────────────────────────────────────

    def test_tool_usage_no_calls(self) -> None:
        assert self._score(tool_calls=0)["tool_usage"] == 1.0

    def test_tool_usage_all_success(self) -> None:
        assert self._score(tool_calls=5, tool_failures=0)["tool_usage"] == 1.0

    def test_tool_usage_some_failures(self) -> None:
        score = self._score(tool_calls=10, tool_failures=3)["tool_usage"]
        assert score == pytest.approx(0.7)

    def test_tool_usage_all_failures(self) -> None:
        assert self._score(tool_calls=5, tool_failures=5)["tool_usage"] == 0.0

    def test_tool_usage_clamp_floor(self) -> None:
        """失败数不应产生负分。"""
        # tool_failures > tool_calls 理论上不应发生，但 max(0,) 保底
        score = self._score(tool_calls=3, tool_failures=5)["tool_usage"]
        assert score == 0.0

    # ── safety ───────────────────────────────────────────

    def test_safety_no_trips(self) -> None:
        assert self._score(guardrail_trips=0)["safety"] == 1.0

    def test_safety_few_trips(self) -> None:
        assert self._score(guardrail_trips=1)["safety"] == 0.5
        assert self._score(guardrail_trips=2)["safety"] == 0.5

    def test_safety_many_trips(self) -> None:
        assert self._score(guardrail_trips=3)["safety"] == 0.2
        assert self._score(guardrail_trips=10)["safety"] == 0.2


# ══════════════════════════════════════════════════════════════
# LearningLoop
# ══════════════════════════════════════════════════════════════


class TestLearningLoop:
    """LearningLoop 端到端自闭环测试。"""

    def test_init_defaults(self) -> None:
        """默认初始化正确。"""
        loop = LearningLoop(agent_name="bot")
        assert loop.agent_name == "bot"
        assert loop.run_count == 0
        assert loop.engine is not None
        assert loop.config.enabled is False

    def test_process_run_increments_count(self) -> None:
        """每次 process_run 递增计数。"""
        loop = LearningLoop(agent_name="bot")
        loop.process_run(_make_trace())
        assert loop.run_count == 1
        loop.process_run(_make_trace())
        assert loop.run_count == 2

    def test_process_run_collects_signals(self) -> None:
        """process_run 将信号写入 collector。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        loop.process_run(_make_trace())
        assert len(collector) == 1
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        assert sig.agent_name == "bot"
        assert sig.signal_type == SignalType.EVALUATION

    def test_process_run_uses_trace_agent_name(self) -> None:
        """当 trace 里有 agent_name 时优先使用。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="default", collector=collector)
        loop.process_run(_make_trace(agent_name="special"))
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        # reflection.agent_name 来自 trace, 但 signal 里 agent_name 由 LearningLoop 决定
        # 查看 _reflection_to_signal: 使用 reflection.agent_name or self.agent_name
        assert sig.agent_name == "special"

    def test_process_run_fallback_agent_name(self) -> None:
        """trace 无 agent_name 时回退到 loop 的 agent_name。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="fallback", collector=collector)
        loop.process_run(_make_trace(agent_name=""))
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        assert sig.agent_name == "fallback"

    def test_no_proposals_by_default(self) -> None:
        """默认配置下 min_samples=50，单次运行不触发建议。"""
        loop = LearningLoop(agent_name="bot")
        proposals = loop.process_run(_make_trace())
        assert proposals == []

    def test_proposals_on_low_score_enough_samples(self) -> None:
        """评分低且样本足够时生成建议。"""
        config = EvolutionConfig(enabled=True, min_samples=1, eval_threshold=0.9)
        collector = SignalCollector()
        loop = LearningLoop(
            agent_name="bot",
            config=config,
            collector=collector,
        )
        # 制造一个全部失败、低效的 trace
        trace = _make_trace(
            status="failed",
            spans=[
                _llm_span(tokens=100),
                _llm_span(tokens=200),
                _llm_span(tokens=300),
                _llm_span(tokens=400),
                _llm_span(tokens=500),
                _llm_span(tokens=600),
                _llm_span(tokens=700),
                _tool_span(status="failed"),
                _tool_span(status="failed"),
                _guardrail_span(status="failed"),
                _guardrail_span(status="failed"),
                _guardrail_span(status="failed"),
            ],
        )
        proposals = loop.process_run(trace)
        assert len(proposals) >= 1
        assert proposals[0].proposal_type == ProposalType.INSTRUCTIONS

    def test_signal_overall_score_computed(self) -> None:
        """信号 overall_score 是四个维度的均值。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        loop.process_run(_make_trace(spans=[_llm_span(tokens=50)]))
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        # accuracy=1.0, efficiency=1.0 (1 turn), tool_usage=1.0 (0 calls), safety=1.0
        assert sig.overall_score == pytest.approx(1.0)

    def test_signal_metadata_contains_run_info(self) -> None:
        """信号 metadata 包含运行信息。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        loop.process_run(_make_trace(trace_id="run-42", spans=[_llm_span(tokens=200)]))
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        assert sig.metadata["run_id"] == "run-42"
        assert sig.metadata["success"] is True
        assert sig.metadata["turn_count"] == 1
        assert sig.metadata["total_tokens"] == 200

    def test_custom_engine(self) -> None:
        """可使用自定义 StrategyEngine。"""
        config = EvolutionConfig()
        engine = StrategyEngine(config=config, strategies=[])
        loop = LearningLoop(agent_name="bot", engine=engine)
        # 空策略列表不生成建议
        proposals = loop.process_run(_make_trace())
        assert proposals == []

    def test_multiple_runs_accumulate_signals(self) -> None:
        """多次运行累积信号。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        for _ in range(5):
            loop.process_run(_make_trace())
        assert len(collector) == 5
        assert loop.run_count == 5

    def test_sample_count_in_signal(self) -> None:
        """信号中的 sample_count 等于已处理的运行次数。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        loop.process_run(_make_trace())
        loop.process_run(_make_trace())
        loop.process_run(_make_trace())
        sig = collector.signals[2]
        assert isinstance(sig, MetricSignal)
        assert sig.sample_count == 3

    def test_failed_run_low_scores(self) -> None:
        """失败的运行产出低评分信号。"""
        collector = SignalCollector()
        loop = LearningLoop(agent_name="bot", collector=collector)
        trace = _make_trace(
            status="failed",
            spans=[
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),
                _llm_span(tokens=500),  # 11 turns → efficiency=0.3
                _tool_span(status="failed"),
                _tool_span(status="ok"),
                _guardrail_span(status="failed"),
                _guardrail_span(status="failed"),
                _guardrail_span(status="failed"),
            ],
        )
        loop.process_run(trace)
        sig = collector.signals[0]
        assert isinstance(sig, MetricSignal)
        # accuracy=0.0 (failed), efficiency=0.3 (11 turns),
        # tool_usage=0.5 (1/2 failed), safety=0.2 (3 trips)
        assert sig.accuracy == 0.0
        assert sig.efficiency == 0.3
        assert sig.tool_usage == pytest.approx(0.5)
        assert sig.safety == 0.2
        expected_overall = (0.0 + 0.3 + 0.5 + 0.2) / 4
        assert sig.overall_score == pytest.approx(expected_overall)


# ══════════════════════════════════════════════════════════════
# 从 __init__.py 导入验证
# ══════════════════════════════════════════════════════════════


class TestEvolutionExports:
    """evolution 包的公开导出验证。"""

    def test_learning_loop_exports(self) -> None:
        """新增的 LearningLoop 相关类型可从包顶层导入。"""
        from kasaya.evolution import (
            LearningLoop,
            RunReflection,
            RunReflector,
        )

        assert LearningLoop is not None
        assert RunReflection is not None
        assert RunReflector is not None

    def test_all_list_complete(self) -> None:
        """__all__ 包含所有新增类型。"""
        import kasaya.evolution as evo

        for name in ("RunReflection", "RunReflector", "LearningLoop"):
            assert name in evo.__all__, f"{name} missing from __all__"
