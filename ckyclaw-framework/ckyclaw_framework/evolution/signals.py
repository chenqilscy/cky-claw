"""进化信号采集。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SignalType(StrEnum):
    """信号类型。"""

    EVALUATION = "evaluation"
    """来自 RunEvaluation 的多维评分信号。"""

    FEEDBACK = "feedback"
    """来自用户反馈（thumbs up/down + 评论）的信号。"""

    TOOL_PERFORMANCE = "tool_performance"
    """来自工具调用成功率/耗时的信号。"""

    GUARDRAIL = "guardrail"
    """来自 Guardrail 触发率的信号。"""

    TOKEN_USAGE = "token_usage"
    """来自 Token 消耗趋势的信号。"""


@dataclass
class EvolutionSignal:
    """进化信号基类。

    每个信号代表一个可用于优化决策的数据点。
    """

    signal_type: SignalType
    """信号类型。"""

    agent_name: str
    """关联的 Agent 名称。"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """信号产生时间。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据。"""


@dataclass
class MetricSignal(EvolutionSignal):
    """评分指标信号。对应 RunEvaluation 的多维评分。"""

    accuracy: float = 0.0
    relevance: float = 0.0
    coherence: float = 0.0
    helpfulness: float = 0.0
    safety: float = 0.0
    efficiency: float = 0.0
    tool_usage: float = 0.0
    overall_score: float = 0.0
    sample_count: int = 0

    def __post_init__(self) -> None:
        """确保信号类型正确。"""
        self.signal_type = SignalType.EVALUATION


@dataclass
class FeedbackSignal(EvolutionSignal):
    """用户反馈信号。对应 RunFeedback 的聚合数据。"""

    positive_count: int = 0
    negative_count: int = 0
    total_count: int = 0
    negative_rate: float = 0.0
    common_complaints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """确保信号类型正确，计算负反馈率。"""
        self.signal_type = SignalType.FEEDBACK
        if self.total_count > 0:
            self.negative_rate = self.negative_count / self.total_count


@dataclass
class ToolPerformanceSignal(EvolutionSignal):
    """工具性能信号。来自 Tracing Spans 的工具调用统计。"""

    tool_name: str = ""
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    failure_rate: float = 0.0
    avg_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        """确保信号类型正确，计算失败率。"""
        self.signal_type = SignalType.TOOL_PERFORMANCE
        if self.call_count > 0:
            self.failure_rate = self.failure_count / self.call_count


class SignalCollector:
    """信号采集器。

    聚合来自不同数据源的进化信号。信号采集本身无副作用，
    仅读取和聚合数据。
    """

    def __init__(self) -> None:
        """初始化空的信号缓冲区。"""
        self._signals: list[EvolutionSignal] = []

    @property
    def signals(self) -> list[EvolutionSignal]:
        """已采集的信号列表（只读视图）。"""
        return list(self._signals)

    def add_signal(self, signal: EvolutionSignal) -> None:
        """添加一条进化信号。

        Args:
            signal: 进化信号实例。
        """
        self._signals.append(signal)

    def get_signals_by_type(self, signal_type: SignalType) -> list[EvolutionSignal]:
        """按类型过滤信号。

        Args:
            signal_type: 目标信号类型。

        Returns:
            匹配的信号列表。
        """
        return [s for s in self._signals if s.signal_type == signal_type]

    def get_signals_for_agent(self, agent_name: str) -> list[EvolutionSignal]:
        """获取指定 Agent 的所有信号。

        Args:
            agent_name: Agent 名称。

        Returns:
            该 Agent 的信号列表。
        """
        return [s for s in self._signals if s.agent_name == agent_name]

    def clear(self) -> None:
        """清空所有已采集信号。"""
        self._signals.clear()

    def __len__(self) -> int:
        """返回已采集信号数量。"""
        return len(self._signals)
