"""Agent Benchmarking 标准化评估套件。

提供 Agent 能力评测基础设施：
- **BenchmarkCase**：单个评测用例（输入 + 预期 + 评分维度）
- **BenchmarkSuite**：评测套件（多个用例 + 配置参数）
- **BenchmarkRunner**：批量执行引擎（并发执行 + 结果采集 + 超时控制）
- **BenchmarkReport**：评测报告（聚合评分 + 维度分布）

与 E2 MaturityModel 集成：评测结果自动影响成熟度评分。
"""

from __future__ import annotations

from ckyclaw_framework.benchmark.case import (
    BenchmarkCase,
    CaseResult,
    CaseStatus,
    EvalDimension,
)
from ckyclaw_framework.benchmark.report import BenchmarkReport, DimensionSummary
from ckyclaw_framework.benchmark.runner import BenchmarkRunner, RunnerConfig
from ckyclaw_framework.benchmark.suite import BenchmarkSuite

__all__ = [
    "BenchmarkCase",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "CaseResult",
    "CaseStatus",
    "DimensionSummary",
    "EvalDimension",
    "RunnerConfig",
]
