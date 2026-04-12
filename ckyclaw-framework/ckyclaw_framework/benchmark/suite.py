"""评测套件定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ckyclaw_framework.benchmark.case import BenchmarkCase


@dataclass
class BenchmarkSuite:
    """评测套件 — 聚合多个用例 + 配置参数。

    Attributes:
        name: 套件名称
        description: 套件描述
        cases: 评测用例列表
        agent_name: 目标 Agent 名称
        model: 使用的模型标识
        concurrency: 并发执行数
        timeout_ms: 单用例超时（毫秒）
        tags: 分类标签
        metadata: 附加元数据
    """

    name: str
    description: str = ""
    cases: list[BenchmarkCase] = field(default_factory=list)
    agent_name: str = ""
    model: str = ""
    concurrency: int = 3
    timeout_ms: int = 30_000
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_case(self, case: BenchmarkCase) -> None:
        """添加评测用例。"""
        self.cases.append(case)

    def filter_by_tag(self, tag: str) -> list[BenchmarkCase]:
        """按标签筛选用例。"""
        return [c for c in self.cases if tag in c.tags]

    @property
    def case_count(self) -> int:
        """用例总数。"""
        return len(self.cases)
