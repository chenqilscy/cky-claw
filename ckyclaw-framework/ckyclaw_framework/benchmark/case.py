"""评测用例定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvalDimension(str, Enum):
    """评估维度。"""

    ACCURACY = "accuracy"
    """工具调用准确率 / 回答正确性。"""

    COHERENCE = "coherence"
    """多轮对话连贯性。"""

    SAFETY = "safety"
    """拒答合规性 / 安全防护。"""

    HALLUCINATION = "hallucination"
    """幻觉率（越低越好，评分取反：1 - hallucination_rate）。"""

    EFFICIENCY = "efficiency"
    """Token 效率 / 响应速度。"""

    TOOL_USAGE = "tool_usage"
    """工具选择与参数准确度。"""


class CaseStatus(str, Enum):
    """用例执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class BenchmarkCase:
    """单个评测用例。

    Attributes:
        name: 用例名称（唯一标识）
        description: 用例描述
        input_messages: 输入消息列表（模拟用户输入）
        expected_output: 预期输出（可选，用于精确匹配）
        expected_tool_calls: 预期调用的工具列表
        eval_dimensions: 评估维度列表
        tags: 分类标签（如 "safety"、"tool-call"、"multi-turn"）
        metadata: 附加元数据
    """

    name: str
    description: str = ""
    input_messages: list[dict[str, str]] = field(default_factory=list)
    expected_output: str | None = None
    expected_tool_calls: list[str] = field(default_factory=list)
    eval_dimensions: list[EvalDimension] = field(
        default_factory=lambda: list(EvalDimension)
    )
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    """单个用例的执行结果。

    Attributes:
        case_name: 关联的用例名称
        status: 执行状态
        actual_output: 实际输出
        actual_tool_calls: 实际调用的工具
        scores: 各维度评分（0.0-1.0）
        latency_ms: 执行耗时（毫秒）
        token_usage: Token 消耗
        error: 错误信息（仅在 ERROR 状态时）
    """

    case_name: str
    status: CaseStatus = CaseStatus.PENDING
    actual_output: str = ""
    actual_tool_calls: list[str] = field(default_factory=list)
    scores: dict[EvalDimension, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def overall_score(self) -> float:
        """计算加权平均分。"""
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    @property
    def passed(self) -> bool:
        """判断是否通过（overall >= 0.6）。"""
        return self.status == CaseStatus.PASSED and self.overall_score >= 0.6
