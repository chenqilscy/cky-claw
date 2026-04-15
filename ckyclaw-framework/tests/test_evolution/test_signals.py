"""进化信号（Signals）测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.evolution.signals import (
    FeedbackSignal,
    MetricSignal,
    SignalCollector,
    SignalType,
    ToolPerformanceSignal,
)


class TestSignalType:
    """SignalType 枚举测试。"""

    def test_values(self) -> None:
        """枚举值完整。"""
        assert SignalType.EVALUATION.value == "evaluation"
        assert SignalType.FEEDBACK.value == "feedback"
        assert SignalType.TOOL_PERFORMANCE.value == "tool_performance"
        assert SignalType.GUARDRAIL.value == "guardrail"
        assert SignalType.TOKEN_USAGE.value == "token_usage"


class TestMetricSignal:
    """MetricSignal 测试。"""

    def test_defaults(self) -> None:
        """默认值正确。"""
        sig = MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot")
        assert sig.signal_type == SignalType.EVALUATION
        assert sig.agent_name == "bot"
        assert sig.overall_score == 0.0
        assert sig.sample_count == 0

    def test_post_init_forces_type(self) -> None:
        """__post_init__ 强制修正 signal_type。"""
        sig = MetricSignal(signal_type=SignalType.FEEDBACK, agent_name="bot")
        assert sig.signal_type == SignalType.EVALUATION

    def test_custom_scores(self) -> None:
        """自定义评分值。"""
        sig = MetricSignal(
            signal_type=SignalType.EVALUATION,
            agent_name="bot",
            accuracy=0.9,
            relevance=0.85,
            overall_score=0.88,
            sample_count=100,
        )
        assert sig.accuracy == 0.9
        assert sig.relevance == 0.85
        assert sig.overall_score == 0.88
        assert sig.sample_count == 100


class TestFeedbackSignal:
    """FeedbackSignal 测试。"""

    def test_negative_rate_calculation(self) -> None:
        """自动计算负反馈率。"""
        sig = FeedbackSignal(
            signal_type=SignalType.FEEDBACK,
            agent_name="bot",
            positive_count=70,
            negative_count=30,
            total_count=100,
        )
        assert sig.signal_type == SignalType.FEEDBACK
        assert sig.negative_rate == pytest.approx(0.3)

    def test_zero_total(self) -> None:
        """total_count=0 时不除零。"""
        sig = FeedbackSignal(
            signal_type=SignalType.FEEDBACK,
            agent_name="bot",
            total_count=0,
        )
        assert sig.negative_rate == 0.0

    def test_common_complaints(self) -> None:
        """常见投诉列表。"""
        sig = FeedbackSignal(
            signal_type=SignalType.FEEDBACK,
            agent_name="bot",
            total_count=10,
            common_complaints=["回答太长", "不够准确"],
        )
        assert len(sig.common_complaints) == 2


class TestToolPerformanceSignal:
    """ToolPerformanceSignal 测试。"""

    def test_failure_rate_calculation(self) -> None:
        """自动计算失败率。"""
        sig = ToolPerformanceSignal(
            signal_type=SignalType.TOOL_PERFORMANCE,
            agent_name="bot",
            tool_name="search_web",
            call_count=50,
            success_count=40,
            failure_count=10,
        )
        assert sig.failure_rate == pytest.approx(0.2)

    def test_zero_calls(self) -> None:
        """call_count=0 时不除零。"""
        sig = ToolPerformanceSignal(
            signal_type=SignalType.TOOL_PERFORMANCE,
            agent_name="bot",
            tool_name="noop",
            call_count=0,
        )
        assert sig.failure_rate == 0.0

    def test_post_init_forces_type(self) -> None:
        """__post_init__ 强制修正 signal_type。"""
        sig = ToolPerformanceSignal(
            signal_type=SignalType.GUARDRAIL,
            agent_name="bot",
            tool_name="test",
        )
        assert sig.signal_type == SignalType.TOOL_PERFORMANCE


class TestSignalCollector:
    """SignalCollector 测试。"""

    def test_empty_collector(self) -> None:
        """空采集器。"""
        collector = SignalCollector()
        assert len(collector) == 0
        assert collector.signals == []

    def test_add_and_get_signals(self) -> None:
        """添加和获取信号。"""
        collector = SignalCollector()
        sig1 = MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot-a")
        sig2 = FeedbackSignal(signal_type=SignalType.FEEDBACK, agent_name="bot-b", total_count=10)
        collector.add_signal(sig1)
        collector.add_signal(sig2)
        assert len(collector) == 2

    def test_get_signals_by_type(self) -> None:
        """按类型过滤。"""
        collector = SignalCollector()
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot"))
        collector.add_signal(FeedbackSignal(signal_type=SignalType.FEEDBACK, agent_name="bot", total_count=5))
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot"))

        evals = collector.get_signals_by_type(SignalType.EVALUATION)
        assert len(evals) == 2
        fbs = collector.get_signals_by_type(SignalType.FEEDBACK)
        assert len(fbs) == 1

    def test_get_signals_for_agent(self) -> None:
        """按 Agent 过滤。"""
        collector = SignalCollector()
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot-a"))
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot-b"))
        collector.add_signal(FeedbackSignal(signal_type=SignalType.FEEDBACK, agent_name="bot-a", total_count=5))

        a_signals = collector.get_signals_for_agent("bot-a")
        assert len(a_signals) == 2
        b_signals = collector.get_signals_for_agent("bot-b")
        assert len(b_signals) == 1

    def test_clear(self) -> None:
        """清空信号。"""
        collector = SignalCollector()
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot"))
        assert len(collector) == 1
        collector.clear()
        assert len(collector) == 0

    def test_signals_returns_copy(self) -> None:
        """signals 属性返回副本，不影响内部状态。"""
        collector = SignalCollector()
        collector.add_signal(MetricSignal(signal_type=SignalType.EVALUATION, agent_name="bot"))
        copy = collector.signals
        copy.clear()
        assert len(collector) == 1
