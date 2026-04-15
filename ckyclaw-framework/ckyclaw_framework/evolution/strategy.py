"""进化策略引擎。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ckyclaw_framework.evolution.config import EvolutionConfig
from ckyclaw_framework.evolution.proposal import EvolutionProposal, ProposalType
from ckyclaw_framework.evolution.signals import (
    EvolutionSignal,
    FeedbackSignal,
    MetricSignal,
    ToolPerformanceSignal,
)


class EvolutionStrategy(Protocol):
    """进化策略协议。

    策略负责分析信号并生成优化建议。
    每种策略关注特定维度的优化（Instructions/Tools/Guardrails 等）。
    """

    def analyze(
        self,
        agent_name: str,
        signals: list[EvolutionSignal],
        config: EvolutionConfig,
    ) -> list[EvolutionProposal]:
        """分析信号并生成优化建议。

        Args:
            agent_name: 目标 Agent 名称。
            signals: 该 Agent 的所有进化信号。
            config: 进化配置。

        Returns:
            生成的优化建议列表（可能为空）。
        """
        ...


@dataclass
class InstructionsOptimizationStrategy:
    """Instructions 优化策略。

    基于评分和反馈信号，生成 Instructions 优化建议。
    当平均评分低于阈值或负反馈率过高时触发。
    """

    def analyze(
        self,
        agent_name: str,
        signals: list[EvolutionSignal],
        config: EvolutionConfig,
    ) -> list[EvolutionProposal]:
        """分析评分和反馈信号，生成 Instructions 优化建议。"""
        proposals: list[EvolutionProposal] = []

        # 检查评分信号
        metric_signals = [s for s in signals if isinstance(s, MetricSignal)]
        if metric_signals:
            latest = metric_signals[-1]
            if latest.sample_count >= config.min_samples and latest.overall_score < config.eval_threshold:
                # 生成 Instructions 优化建议
                weak_dims = self._find_weak_dimensions(latest)
                proposals.append(EvolutionProposal(
                    agent_name=agent_name,
                    proposal_type=ProposalType.INSTRUCTIONS,
                    trigger_reason=(
                        f"平均评分 {latest.overall_score:.2f} 低于阈值 {config.eval_threshold}，"
                        f"薄弱维度: {', '.join(weak_dims)}"
                    ),
                    confidence_score=min(0.9, 1.0 - latest.overall_score),
                    metadata={
                        "weak_dimensions": weak_dims,
                        "current_scores": {
                            "accuracy": latest.accuracy,
                            "relevance": latest.relevance,
                            "coherence": latest.coherence,
                            "helpfulness": latest.helpfulness,
                            "safety": latest.safety,
                            "efficiency": latest.efficiency,
                            "tool_usage": latest.tool_usage,
                        },
                        "sample_count": latest.sample_count,
                    },
                ))

        # 检查反馈信号
        feedback_signals = [s for s in signals if isinstance(s, FeedbackSignal)]
        if feedback_signals:
            latest_fb = feedback_signals[-1]
            if (
                latest_fb.total_count >= config.min_samples
                and latest_fb.negative_rate > config.feedback_negative_rate
            ):
                proposals.append(EvolutionProposal(
                    agent_name=agent_name,
                    proposal_type=ProposalType.INSTRUCTIONS,
                    trigger_reason=(
                        f"负反馈率 {latest_fb.negative_rate:.1%} 超过阈值 {config.feedback_negative_rate:.1%}，"
                        f"常见投诉: {', '.join(latest_fb.common_complaints[:3])}"
                    ),
                    confidence_score=min(0.8, latest_fb.negative_rate),
                    metadata={
                        "positive_count": latest_fb.positive_count,
                        "negative_count": latest_fb.negative_count,
                        "common_complaints": latest_fb.common_complaints,
                    },
                ))

        return proposals

    @staticmethod
    def _find_weak_dimensions(signal: MetricSignal, threshold: float = 0.6) -> list[str]:
        """找出低于阈值的评分维度。"""
        dims: list[str] = []
        for dim_name, dim_value in [
            ("accuracy", signal.accuracy),
            ("relevance", signal.relevance),
            ("coherence", signal.coherence),
            ("helpfulness", signal.helpfulness),
            ("safety", signal.safety),
            ("efficiency", signal.efficiency),
            ("tool_usage", signal.tool_usage),
        ]:
            if dim_value < threshold:
                dims.append(dim_name)
        return dims


@dataclass
class ToolOptimizationStrategy:
    """工具优化策略。

    基于工具调用成功率和耗时，生成工具配置优化建议。
    当某工具失败率过高时建议禁用或替换。
    """

    def analyze(
        self,
        agent_name: str,
        signals: list[EvolutionSignal],
        config: EvolutionConfig,
    ) -> list[EvolutionProposal]:
        """分析工具性能信号，生成工具优化建议。"""
        proposals: list[EvolutionProposal] = []

        tool_signals = [s for s in signals if isinstance(s, ToolPerformanceSignal)]
        for sig in tool_signals:
            if sig.call_count >= 10 and sig.failure_rate > config.tool_failure_rate:
                proposals.append(EvolutionProposal(
                    agent_name=agent_name,
                    proposal_type=ProposalType.TOOLS,
                    trigger_reason=(
                        f"工具 '{sig.tool_name}' 失败率 {sig.failure_rate:.1%} 超过阈值 "
                        f"{config.tool_failure_rate:.1%}（{sig.failure_count}/{sig.call_count}）"
                    ),
                    confidence_score=min(0.9, sig.failure_rate),
                    metadata={
                        "tool_name": sig.tool_name,
                        "call_count": sig.call_count,
                        "failure_count": sig.failure_count,
                        "failure_rate": sig.failure_rate,
                        "avg_duration_ms": sig.avg_duration_ms,
                    },
                ))

        return proposals


@dataclass
class StrategyEngine:
    """策略引擎。

    管理多个进化策略，协调信号分析和建议生成。
    """

    config: EvolutionConfig = field(default_factory=EvolutionConfig)
    """进化配置。"""

    strategies: list[EvolutionStrategy] = field(default_factory=list)
    """已注册的策略列表。"""

    def __post_init__(self) -> None:
        """如果没有指定策略则使用默认策略集。"""
        if not self.strategies:
            self.strategies = [
                InstructionsOptimizationStrategy(),
                ToolOptimizationStrategy(),
            ]

    def add_strategy(self, strategy: EvolutionStrategy) -> None:
        """注册新的进化策略。

        Args:
            strategy: 实现 EvolutionStrategy 协议的策略实例。
        """
        self.strategies.append(strategy)

    def generate_proposals(
        self,
        agent_name: str,
        signals: list[EvolutionSignal],
    ) -> list[EvolutionProposal]:
        """从所有策略生成优化建议。

        逐个策略分析信号，合并建议结果，
        限制总数不超过 config.max_proposals_per_cycle。

        Args:
            agent_name: 目标 Agent 名称。
            signals: 该 Agent 的所有进化信号。

        Returns:
            优化建议列表（已按置信度降序排列，截断为 max_proposals_per_cycle）。
        """
        if not self.config.enabled:
            return []

        all_proposals: list[EvolutionProposal] = []
        for strategy in self.strategies:
            proposals = strategy.analyze(agent_name, signals, self.config)
            all_proposals.extend(proposals)

        # 按置信度降序排列，截断
        all_proposals.sort(key=lambda p: p.confidence_score, reverse=True)
        return all_proposals[: self.config.max_proposals_per_cycle]
