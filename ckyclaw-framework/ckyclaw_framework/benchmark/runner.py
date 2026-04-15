"""评测执行引擎。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.benchmark.case import (
    BenchmarkCase,
    CaseResult,
    CaseStatus,
    EvalDimension,
)
from ckyclaw_framework.benchmark.report import BenchmarkReport

if TYPE_CHECKING:
    from ckyclaw_framework.benchmark.suite import BenchmarkSuite

logger = logging.getLogger(__name__)

# 评分函数类型：(case, actual_output, actual_tool_calls) → dict[EvalDimension, float]
ScorerFn = Callable[
    [BenchmarkCase, str, list[str]],
    Coroutine[Any, Any, dict[EvalDimension, float]],
]


@dataclass
class RunnerConfig:
    """运行器配置。

    Attributes:
        concurrency: 并发执行数
        timeout_ms: 单用例超时（毫秒）
        pass_threshold: 通过阈值（overall >= 此值视为 PASSED）
        retry_on_error: 错误时重试次数
    """

    concurrency: int = 3
    timeout_ms: int = 30_000
    pass_threshold: float = 0.6
    retry_on_error: int = 0


class BenchmarkRunner:
    """评测执行引擎。

    负责批量执行评测用例，采集结果，生成报告。

    用法::

        runner = BenchmarkRunner(
            agent_fn=my_agent_function,
            scorer_fn=my_scorer,
        )
        report = await runner.run(suite)
    """

    def __init__(
        self,
        agent_fn: Callable[..., Any],
        scorer_fn: Callable[..., Any] | None = None,
        config: RunnerConfig | None = None,
    ) -> None:
        """初始化执行引擎。

        Args:
            agent_fn: Agent 调用函数，签名 async (messages: list[dict]) → (output: str, tool_calls: list[str])
            scorer_fn: 评分函数，签名 async (case, output, tool_calls) → dict[EvalDimension, float]
            config: 运行器配置
        """
        self._agent_fn = agent_fn
        self._scorer_fn = scorer_fn
        self._config = config or RunnerConfig()

    async def run(self, suite: BenchmarkSuite) -> BenchmarkReport:
        """执行评测套件。

        Args:
            suite: 评测套件

        Returns:
            评测报告
        """
        report = BenchmarkReport(
            suite_name=suite.name,
            agent_name=suite.agent_name,
            model=suite.model,
        )

        concurrency = suite.concurrency or self._config.concurrency
        timeout_ms = suite.timeout_ms or self._config.timeout_ms
        semaphore = asyncio.Semaphore(concurrency)

        async def _run_one(case: BenchmarkCase) -> CaseResult:
            async with semaphore:
                return await self._execute_case(case, timeout_ms)

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_run_one(c)) for c in suite.cases]

        report.results = [t.result() for t in tasks]
        report.compute_summaries()
        return report

    async def _execute_case(
        self, case: BenchmarkCase, timeout_ms: int
    ) -> CaseResult:
        """执行单个用例。"""
        result = CaseResult(case_name=case.name, status=CaseStatus.RUNNING)
        start = time.monotonic()

        try:
            output, tool_calls = await asyncio.wait_for(
                self._agent_fn(case.input_messages),
                timeout=timeout_ms / 1000,
            )
            result.actual_output = output or ""
            result.actual_tool_calls = tool_calls or []
            result.latency_ms = (time.monotonic() - start) * 1000

            # 评分
            if self._scorer_fn:
                result.scores = await self._scorer_fn(case, output, tool_calls)
            else:
                result.scores = self._default_score(case, output, tool_calls)

            # 判定通过/失败
            result.status = (
                CaseStatus.PASSED
                if result.overall_score >= self._config.pass_threshold
                else CaseStatus.FAILED
            )

        except TimeoutError:
            result.status = CaseStatus.TIMEOUT
            result.error = f"用例超时（{timeout_ms}ms）"
            result.latency_ms = timeout_ms

        except Exception as exc:
            result.status = CaseStatus.ERROR
            result.error = str(exc)
            result.latency_ms = (time.monotonic() - start) * 1000
            logger.warning("评测用例 %s 执行异常: %s", case.name, exc)

        return result

    def _default_score(
        self,
        case: BenchmarkCase,
        output: str,
        tool_calls: list[str],
    ) -> dict[EvalDimension, float]:
        """默认评分器：基于规则匹配。"""
        scores: dict[EvalDimension, float] = {}

        for dim in case.eval_dimensions:
            if dim == EvalDimension.ACCURACY:
                # 如果有预期输出，检查是否包含
                if case.expected_output:
                    scores[dim] = (
                        1.0 if case.expected_output in output else 0.0
                    )
                else:
                    scores[dim] = 1.0 if output.strip() else 0.0

            elif dim == EvalDimension.TOOL_USAGE:
                # 检查工具调用是否匹配
                if case.expected_tool_calls:
                    expected = set(case.expected_tool_calls)
                    actual = set(tool_calls)
                    if not expected:
                        scores[dim] = 1.0
                    else:
                        scores[dim] = len(expected & actual) / len(expected)
                else:
                    scores[dim] = 1.0

            elif dim == EvalDimension.SAFETY:
                # 默认安全得分 1.0，除非输出为空
                scores[dim] = 1.0 if output.strip() else 0.0

            else:
                # 其他维度默认 0.5（由 LLM 评分器覆盖）
                scores[dim] = 0.5

        return scores
