"""评测报告生成。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ckyclaw_framework.benchmark.case import CaseResult, CaseStatus, EvalDimension


@dataclass
class DimensionSummary:
    """单个维度的统计摘要。"""

    dimension: EvalDimension
    mean: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    count: int = 0


@dataclass
class BenchmarkReport:
    """评测报告 — 聚合多个用例结果。

    Attributes:
        suite_name: 套件名称
        agent_name: Agent 名称
        model: 模型标识
        results: 用例结果列表
        started_at: 开始时间
        finished_at: 结束时间
        dimension_summaries: 维度统计
    """

    suite_name: str
    agent_name: str = ""
    model: str = ""
    results: list[CaseResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    dimension_summaries: list[DimensionSummary] = field(default_factory=list)

    @property
    def total_cases(self) -> int:
        """用例总数。"""
        return len(self.results)

    @property
    def passed_cases(self) -> int:
        """通过用例数。"""
        return sum(1 for r in self.results if r.status == CaseStatus.PASSED)

    @property
    def failed_cases(self) -> int:
        """失败用例数。"""
        return sum(1 for r in self.results if r.status == CaseStatus.FAILED)

    @property
    def error_cases(self) -> int:
        """错误用例数。"""
        return sum(1 for r in self.results if r.status == CaseStatus.ERROR)

    @property
    def pass_rate(self) -> float:
        """通过率。"""
        if not self.results:
            return 0.0
        return self.passed_cases / len(self.results)

    @property
    def overall_score(self) -> float:
        """全局加权平均分。"""
        scores = [r.overall_score for r in self.results if r.scores]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @property
    def total_latency_ms(self) -> float:
        """总耗时（毫秒）。"""
        return sum(r.latency_ms for r in self.results)

    @property
    def total_tokens(self) -> int:
        """总 Token 消耗。"""
        return sum(r.token_usage.get("total_tokens", 0) for r in self.results)

    def compute_summaries(self) -> None:
        """计算各维度统计摘要。"""
        dim_scores: dict[EvalDimension, list[float]] = {}
        for r in self.results:
            for dim, score in r.scores.items():
                dim_scores.setdefault(dim, []).append(score)

        self.dimension_summaries = []
        for dim, scores in dim_scores.items():
            self.dimension_summaries.append(
                DimensionSummary(
                    dimension=dim,
                    mean=sum(scores) / len(scores),
                    min_score=min(scores),
                    max_score=max(scores),
                    count=len(scores),
                )
            )
