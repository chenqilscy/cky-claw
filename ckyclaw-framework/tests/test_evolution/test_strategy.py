"""策略引擎（Strategy）测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.evolution.config import EvolutionConfig
from ckyclaw_framework.evolution.proposal import EvolutionProposal, ProposalType
from ckyclaw_framework.evolution.signals import (
    EvolutionSignal,
    FeedbackSignal,
    MetricSignal,
    SignalType,
    ToolPerformanceSignal,
)
from ckyclaw_framework.evolution.strategy import (
    InstructionsOptimizationStrategy,
    StrategyEngine,
    ToolOptimizationStrategy,
)


class TestInstructionsOptimizationStrategy:
    """Instructions 优化策略测试。"""

    def test_low_score_triggers_proposal(self) -> None:
        """评分低于阈值时触发优化建议。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10, eval_threshold=0.7)
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.52,
                accuracy=0.4,
                relevance=0.8,
                coherence=0.9,
                helpfulness=0.3,
                safety=0.9,
                efficiency=0.5,
                tool_usage=0.6,
                sample_count=100,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 1
        assert proposals[0].proposal_type == ProposalType.INSTRUCTIONS
        assert "0.52" in proposals[0].trigger_reason
        assert proposals[0].confidence_score > 0

    def test_high_score_no_proposal(self) -> None:
        """评分高于阈值时不触发。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10, eval_threshold=0.7)
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.85,
                sample_count=100,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 0

    def test_insufficient_samples_no_proposal(self) -> None:
        """样本不足时不触发。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=100, eval_threshold=0.7)
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.3,
                sample_count=50,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 0

    def test_negative_feedback_triggers_proposal(self) -> None:
        """负反馈率超阈值时触发。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10, feedback_negative_rate=0.3)
        signals: list[EvolutionSignal] = [
            FeedbackSignal(
                signal_type=SignalType.FEEDBACK,
                agent_name="bot",
                positive_count=30,
                negative_count=70,
                total_count=100,
                common_complaints=["回答太长", "不够准确", "幻觉"],
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 1
        assert "负反馈率" in proposals[0].trigger_reason
        assert "回答太长" in proposals[0].trigger_reason

    def test_low_negative_rate_no_proposal(self) -> None:
        """负反馈率低于阈值时不触发。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10, feedback_negative_rate=0.3)
        signals: list[EvolutionSignal] = [
            FeedbackSignal(
                signal_type=SignalType.FEEDBACK,
                agent_name="bot",
                positive_count=90,
                negative_count=10,
                total_count=100,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 0

    def test_both_triggers(self) -> None:
        """评分低 + 负反馈高同时触发两条建议。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10, eval_threshold=0.7, feedback_negative_rate=0.3)
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.5,
                sample_count=100,
            ),
            FeedbackSignal(
                signal_type=SignalType.FEEDBACK,
                agent_name="bot",
                negative_count=50,
                total_count=100,
                common_complaints=["太慢"],
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 2

    def test_find_weak_dimensions(self) -> None:
        """_find_weak_dimensions 正确找出低分维度。"""
        sig = MetricSignal(
            signal_type=SignalType.EVALUATION,
            agent_name="bot",
            accuracy=0.9,
            relevance=0.3,  # < 0.6
            coherence=0.5,  # < 0.6
            helpfulness=0.8,
            safety=0.95,
            efficiency=0.4,  # < 0.6
            tool_usage=0.7,
        )
        weak = InstructionsOptimizationStrategy._find_weak_dimensions(sig)
        assert set(weak) == {"relevance", "coherence", "efficiency"}

    def test_no_signals_no_proposals(self) -> None:
        """无信号时不生成建议。"""
        strategy = InstructionsOptimizationStrategy()
        config = EvolutionConfig(min_samples=10)
        proposals = strategy.analyze("bot", [], config)
        assert len(proposals) == 0


class TestToolOptimizationStrategy:
    """工具优化策略测试。"""

    def test_high_failure_triggers_proposal(self) -> None:
        """高失败率触发建议。"""
        strategy = ToolOptimizationStrategy()
        config = EvolutionConfig(tool_failure_rate=0.2)
        signals: list[EvolutionSignal] = [
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="buggy_tool",
                call_count=100,
                success_count=50,
                failure_count=50,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 1
        assert proposals[0].proposal_type == ProposalType.TOOLS
        assert "buggy_tool" in proposals[0].trigger_reason

    def test_low_failure_no_proposal(self) -> None:
        """低失败率不触发。"""
        strategy = ToolOptimizationStrategy()
        config = EvolutionConfig(tool_failure_rate=0.2)
        signals: list[EvolutionSignal] = [
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="good_tool",
                call_count=100,
                success_count=95,
                failure_count=5,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 0

    def test_insufficient_calls_no_proposal(self) -> None:
        """调用次数不足时不触发（低于 10 次）。"""
        strategy = ToolOptimizationStrategy()
        config = EvolutionConfig(tool_failure_rate=0.2)
        signals: list[EvolutionSignal] = [
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="rare_tool",
                call_count=5,
                failure_count=3,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 0

    def test_multiple_tools(self) -> None:
        """多个工具都超阈值时生成多条建议。"""
        strategy = ToolOptimizationStrategy()
        config = EvolutionConfig(tool_failure_rate=0.2)
        signals: list[EvolutionSignal] = [
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="tool_a",
                call_count=50,
                failure_count=20,
            ),
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="tool_b",
                call_count=30,
                failure_count=15,
            ),
        ]
        proposals = strategy.analyze("bot", signals, config)
        assert len(proposals) == 2


class TestStrategyEngine:
    """StrategyEngine 测试。"""

    def test_disabled_returns_empty(self) -> None:
        """config.enabled=False 时返回空列表。"""
        engine = StrategyEngine(config=EvolutionConfig(enabled=False))
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.3,
                sample_count=100,
            ),
        ]
        proposals = engine.generate_proposals("bot", signals)
        assert proposals == []

    def test_default_strategies(self) -> None:
        """默认包含 Instructions 和 Tool 两个策略。"""
        engine = StrategyEngine()
        assert len(engine.strategies) == 2

    def test_generates_proposals(self) -> None:
        """正常生成建议。"""
        engine = StrategyEngine(config=EvolutionConfig(enabled=True, min_samples=10))
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.4,
                sample_count=100,
            ),
        ]
        proposals = engine.generate_proposals("bot", signals)
        assert len(proposals) >= 1

    def test_max_proposals_limit(self) -> None:
        """建议数量限制。"""
        engine = StrategyEngine(
            config=EvolutionConfig(enabled=True, min_samples=5, max_proposals_per_cycle=1),
        )
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.3,
                sample_count=100,
            ),
            FeedbackSignal(
                signal_type=SignalType.FEEDBACK,
                agent_name="bot",
                negative_count=80,
                total_count=100,
                common_complaints=["差"],
            ),
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="bad_tool",
                call_count=100,
                failure_count=50,
            ),
        ]
        proposals = engine.generate_proposals("bot", signals)
        assert len(proposals) <= 1

    def test_sorted_by_confidence(self) -> None:
        """建议按置信度降序排列。"""
        engine = StrategyEngine(
            config=EvolutionConfig(enabled=True, min_samples=5, max_proposals_per_cycle=10),
        )
        signals: list[EvolutionSignal] = [
            MetricSignal(
                signal_type=SignalType.EVALUATION,
                agent_name="bot",
                overall_score=0.5,
                sample_count=100,
            ),
            ToolPerformanceSignal(
                signal_type=SignalType.TOOL_PERFORMANCE,
                agent_name="bot",
                tool_name="bad_tool",
                call_count=100,
                failure_count=90,
            ),
        ]
        proposals = engine.generate_proposals("bot", signals)
        if len(proposals) >= 2:
            assert proposals[0].confidence_score >= proposals[1].confidence_score

    def test_add_strategy(self) -> None:
        """注册自定义策略。"""

        class DummyStrategy:
            def analyze(
                self,
                agent_name: str,
                signals: list[EvolutionSignal],
                config: EvolutionConfig,
            ) -> list[EvolutionProposal]:
                return [
                    EvolutionProposal(
                        agent_name=agent_name,
                        proposal_type=ProposalType.MODEL,
                        trigger_reason="dummy",
                        confidence_score=1.0,
                    ),
                ]

        engine = StrategyEngine(config=EvolutionConfig(enabled=True))
        engine.add_strategy(DummyStrategy())
        assert len(engine.strategies) == 3  # 2 default + 1 custom

        proposals = engine.generate_proposals("bot", [])
        # DummyStrategy 无条件生成建议
        assert any(p.proposal_type == ProposalType.MODEL for p in proposals)
