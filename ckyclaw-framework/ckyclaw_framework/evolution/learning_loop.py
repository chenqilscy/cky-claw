"""LearningLoop — 运行反思 → 信号采集 → 建议生成的自闭环。

LearningLoop 在每次运行结束后自动执行：
1. RunReflector 从 Trace 数据评估运行质量
2. 将评估结果转换为 MetricSignal / FeedbackSignal
3. StrategyEngine 分析信号并生成 EvolutionProposal
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.evolution.config import EvolutionConfig
from ckyclaw_framework.evolution.signals import (
    MetricSignal,
    SignalCollector,
    SignalType,
)
from ckyclaw_framework.evolution.strategy import StrategyEngine

if TYPE_CHECKING:
    from ckyclaw_framework.evolution.proposal import EvolutionProposal

logger = logging.getLogger(__name__)


@dataclass
class RunReflection:
    """单次运行的反思结果。"""

    run_id: str = ""
    """运行 ID。"""

    agent_name: str = ""
    """Agent 名称。"""

    success: bool = True
    """运行是否成功。"""

    turn_count: int = 0
    """LLM 调用轮次。"""

    tool_calls: int = 0
    """工具调用次数。"""

    tool_failures: int = 0
    """工具调用失败次数。"""

    guardrail_trips: int = 0
    """护栏触发次数。"""

    total_tokens: int = 0
    """总 Token 消耗。"""

    duration_ms: int = 0
    """运行总耗时（毫秒）。"""

    error_message: str = ""
    """错误信息（如有）。"""

    scores: dict[str, float] = field(default_factory=dict)
    """各维度评分（0-1）：accuracy, efficiency, safety 等。"""


class RunReflector:
    """从 Trace 数据中提取运行反思。

    分析 Trace 中的 Span 信息，计算各维度评分，
    生成 RunReflection 结构化数据。
    """

    def reflect(self, trace_data: dict[str, Any]) -> RunReflection:
        """从 trace 数据生成反思结果。

        Args:
            trace_data: Trace 的字典表示，包含 spans、duration 等信息。

        Returns:
            运行反思结果。
        """
        spans = trace_data.get("spans", [])
        reflection = RunReflection(
            run_id=trace_data.get("trace_id", ""),
            agent_name=trace_data.get("agent_name", ""),
            success=trace_data.get("status", "") != "failed",
            duration_ms=trace_data.get("duration_ms", 0),
        )

        for span in spans:
            span_type = span.get("type", "")
            status = span.get("status", "")

            if span_type == "llm":
                reflection.turn_count += 1
                usage = span.get("token_usage") or {}
                reflection.total_tokens += usage.get("total_tokens", 0)

            elif span_type == "tool":
                reflection.tool_calls += 1
                if status == "failed":
                    reflection.tool_failures += 1

            elif span_type == "guardrail" and status == "failed":
                reflection.guardrail_trips += 1

        # 计算各维度评分
        reflection.scores = self._compute_scores(reflection)
        return reflection

    def _compute_scores(self, r: RunReflection) -> dict[str, float]:
        """根据运行指标计算各维度评分。"""
        scores: dict[str, float] = {}

        # 成功率：成功=1.0, 失败=0.0
        scores["accuracy"] = 1.0 if r.success else 0.0

        # 效率：基于轮次和 Token 的简单评估
        if r.turn_count <= 3:
            scores["efficiency"] = 1.0
        elif r.turn_count <= 6:
            scores["efficiency"] = 0.7
        elif r.turn_count <= 10:
            scores["efficiency"] = 0.5
        else:
            scores["efficiency"] = 0.3

        # 工具使用质量
        if r.tool_calls == 0:
            scores["tool_usage"] = 1.0
        else:
            scores["tool_usage"] = max(0.0, 1.0 - (r.tool_failures / r.tool_calls))

        # 安全性：护栏触发越多越低
        if r.guardrail_trips == 0:
            scores["safety"] = 1.0
        elif r.guardrail_trips <= 2:
            scores["safety"] = 0.5
        else:
            scores["safety"] = 0.2

        return scores


@dataclass
class LearningLoop:
    """自改进闭环。

    在每次运行结束后执行反思→信号→建议的完整流程。

    用法::

        loop = LearningLoop(agent_name="bot")
        proposals = loop.process_run(trace_data)
    """

    agent_name: str = ""
    """目标 Agent 名称。"""

    config: EvolutionConfig = field(default_factory=EvolutionConfig)
    """进化配置。"""

    collector: SignalCollector = field(default_factory=SignalCollector)
    """信号采集器。"""

    engine: StrategyEngine | None = None
    """策略引擎（默认自动创建）。"""

    reflector: RunReflector = field(default_factory=RunReflector)
    """运行反思器。"""

    _run_count: int = field(default=0, repr=False)
    """已处理的运行次数。"""

    def __post_init__(self) -> None:
        """初始化策略引擎。"""
        if self.engine is None:
            self.engine = StrategyEngine(config=self.config)

    def process_run(self, trace_data: dict[str, Any]) -> list[EvolutionProposal]:
        """处理一次运行：反思 → 信号采集 → 建议生成。

        Args:
            trace_data: Trace 的字典表示。

        Returns:
            生成的优化建议列表（可能为空）。
        """
        self._run_count += 1

        # Step 1: 反思
        reflection = self.reflector.reflect(trace_data)
        if not reflection.agent_name:
            reflection.agent_name = self.agent_name

        # Step 2: 转换为信号
        signal = self._reflection_to_signal(reflection)
        self.collector.add_signal(signal)

        # Step 3: 生成建议
        assert self.engine is not None
        proposals = self.engine.generate_proposals(
            agent_name=self.agent_name,
            signals=self.collector.signals,
        )

        if proposals:
            logger.info(
                "LearningLoop: agent=%s run=%d generated %d proposals",
                self.agent_name,
                self._run_count,
                len(proposals),
            )

        return proposals

    @property
    def run_count(self) -> int:
        """已处理的运行次数。"""
        return self._run_count

    def _reflection_to_signal(self, reflection: RunReflection) -> MetricSignal:
        """将反思结果转换为 MetricSignal。"""
        scores = reflection.scores
        return MetricSignal(
            agent_name=reflection.agent_name or self.agent_name,
            signal_type=SignalType.EVALUATION,
            overall_score=sum(scores.values()) / max(len(scores), 1),
            accuracy=scores.get("accuracy", 0.0),
            relevance=scores.get("relevance", 0.0),
            coherence=scores.get("coherence", 0.0),
            helpfulness=scores.get("helpfulness", 0.0),
            safety=scores.get("safety", 0.0),
            efficiency=scores.get("efficiency", 0.0),
            tool_usage=scores.get("tool_usage", 0.0),
            sample_count=self._run_count,
            metadata={
                "run_id": reflection.run_id,
                "success": reflection.success,
                "turn_count": reflection.turn_count,
                "total_tokens": reflection.total_tokens,
            },
        )
