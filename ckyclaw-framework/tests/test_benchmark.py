"""N7 Agent Benchmarking 测试。"""

from __future__ import annotations

import asyncio

import pytest

from ckyclaw_framework.benchmark import (
    BenchmarkCase,
    BenchmarkReport,
    BenchmarkRunner,
    BenchmarkSuite,
    CaseResult,
    CaseStatus,
    DimensionSummary,
    EvalDimension,
    RunnerConfig,
)


# ── Case 测试 ──

class TestBenchmarkCase:
    def test_create_case(self) -> None:
        case = BenchmarkCase(
            name="test-case",
            input_messages=[{"role": "user", "content": "hi"}],
            expected_output="hello",
        )
        assert case.name == "test-case"
        assert len(case.input_messages) == 1

    def test_case_defaults(self) -> None:
        case = BenchmarkCase(name="x")
        assert case.description == ""
        assert case.expected_output is None
        assert case.expected_tool_calls == []
        assert len(case.eval_dimensions) == len(EvalDimension)

    def test_case_tags(self) -> None:
        case = BenchmarkCase(name="safety", tags=["safety", "v1"])
        assert "safety" in case.tags


class TestCaseResult:
    def test_overall_score(self) -> None:
        r = CaseResult(
            case_name="c",
            scores={EvalDimension.ACCURACY: 0.8, EvalDimension.SAFETY: 0.6},
        )
        assert r.overall_score == pytest.approx(0.7)

    def test_overall_score_empty(self) -> None:
        r = CaseResult(case_name="c")
        assert r.overall_score == 0.0

    def test_passed_true(self) -> None:
        r = CaseResult(
            case_name="c",
            status=CaseStatus.PASSED,
            scores={EvalDimension.ACCURACY: 0.8},
        )
        assert r.passed is True

    def test_passed_false_low_score(self) -> None:
        r = CaseResult(
            case_name="c",
            status=CaseStatus.PASSED,
            scores={EvalDimension.ACCURACY: 0.3},
        )
        assert r.passed is False


# ── Suite 测试 ──

class TestBenchmarkSuite:
    def test_add_case(self) -> None:
        suite = BenchmarkSuite(name="s")
        suite.add_case(BenchmarkCase(name="c1"))
        assert suite.case_count == 1

    def test_filter_by_tag(self) -> None:
        suite = BenchmarkSuite(name="s", cases=[
            BenchmarkCase(name="a", tags=["safety"]),
            BenchmarkCase(name="b", tags=["tool"]),
            BenchmarkCase(name="c", tags=["safety", "tool"]),
        ])
        assert len(suite.filter_by_tag("safety")) == 2
        assert len(suite.filter_by_tag("tool")) == 2
        assert len(suite.filter_by_tag("unknown")) == 0


# ── Report 测试 ──

class TestBenchmarkReport:
    def _results(self) -> list[CaseResult]:
        return [
            CaseResult(
                case_name="c1",
                status=CaseStatus.PASSED,
                scores={EvalDimension.ACCURACY: 0.9, EvalDimension.SAFETY: 0.8},
                latency_ms=100,
                token_usage={"total_tokens": 50},
            ),
            CaseResult(
                case_name="c2",
                status=CaseStatus.FAILED,
                scores={EvalDimension.ACCURACY: 0.3},
                latency_ms=200,
                token_usage={"total_tokens": 30},
            ),
            CaseResult(
                case_name="c3",
                status=CaseStatus.ERROR,
                error="boom",
                latency_ms=50,
            ),
        ]

    def test_counts(self) -> None:
        report = BenchmarkReport(suite_name="s", results=self._results())
        assert report.total_cases == 3
        assert report.passed_cases == 1
        assert report.failed_cases == 1
        assert report.error_cases == 1

    def test_pass_rate(self) -> None:
        report = BenchmarkReport(suite_name="s", results=self._results())
        assert report.pass_rate == pytest.approx(1 / 3)

    def test_pass_rate_empty(self) -> None:
        report = BenchmarkReport(suite_name="s")
        assert report.pass_rate == 0.0

    def test_total_latency(self) -> None:
        report = BenchmarkReport(suite_name="s", results=self._results())
        assert report.total_latency_ms == 350

    def test_total_tokens(self) -> None:
        report = BenchmarkReport(suite_name="s", results=self._results())
        assert report.total_tokens == 80

    def test_compute_summaries(self) -> None:
        report = BenchmarkReport(suite_name="s", results=self._results())
        report.compute_summaries()
        assert len(report.dimension_summaries) >= 1
        acc = next(
            (s for s in report.dimension_summaries if s.dimension == EvalDimension.ACCURACY),
            None,
        )
        assert acc is not None
        assert acc.count == 2
        assert acc.mean == pytest.approx(0.6)


# ── Runner 测试 ──

class TestBenchmarkRunner:
    @pytest.mark.asyncio
    async def test_run_basic(self) -> None:
        """基本执行流程。"""

        async def agent_fn(messages: list[dict]) -> tuple[str, list[str]]:
            return "hello world", ["tool_a"]

        suite = BenchmarkSuite(
            name="basic",
            agent_name="test-agent",
            cases=[
                BenchmarkCase(
                    name="c1",
                    input_messages=[{"role": "user", "content": "hi"}],
                    expected_output="hello",
                    expected_tool_calls=["tool_a"],
                    eval_dimensions=[EvalDimension.ACCURACY, EvalDimension.TOOL_USAGE],
                ),
            ],
        )

        runner = BenchmarkRunner(agent_fn=agent_fn)
        report = await runner.run(suite)

        assert report.total_cases == 1
        assert report.results[0].status == CaseStatus.PASSED
        assert report.results[0].scores[EvalDimension.ACCURACY] == 1.0
        assert report.results[0].scores[EvalDimension.TOOL_USAGE] == 1.0

    @pytest.mark.asyncio
    async def test_run_timeout(self) -> None:
        """执行超时。"""

        async def slow_agent(messages: list[dict]) -> tuple[str, list[str]]:
            await asyncio.sleep(5)
            return "done", []

        suite = BenchmarkSuite(
            name="timeout",
            cases=[BenchmarkCase(name="slow")],
            timeout_ms=100,
        )

        runner = BenchmarkRunner(agent_fn=slow_agent)
        report = await runner.run(suite)

        assert report.results[0].status == CaseStatus.TIMEOUT
        assert report.results[0].error is not None

    @pytest.mark.asyncio
    async def test_run_error(self) -> None:
        """执行异常。"""

        async def bad_agent(messages: list[dict]) -> tuple[str, list[str]]:
            raise RuntimeError("boom")

        suite = BenchmarkSuite(
            name="error",
            cases=[BenchmarkCase(name="bad")],
        )

        runner = BenchmarkRunner(agent_fn=bad_agent)
        report = await runner.run(suite)

        assert report.results[0].status == CaseStatus.ERROR
        assert "boom" in (report.results[0].error or "")

    @pytest.mark.asyncio
    async def test_run_with_custom_scorer(self) -> None:
        """自定义评分器。"""

        async def agent_fn(messages: list[dict]) -> tuple[str, list[str]]:
            return "ok", []

        async def scorer(case: BenchmarkCase, output: str, tools: list[str]) -> dict:
            return {EvalDimension.ACCURACY: 0.99}

        suite = BenchmarkSuite(
            name="custom-scorer",
            cases=[BenchmarkCase(name="c")],
        )

        runner = BenchmarkRunner(agent_fn=agent_fn, scorer_fn=scorer)
        report = await runner.run(suite)

        assert report.results[0].scores[EvalDimension.ACCURACY] == 0.99

    @pytest.mark.asyncio
    async def test_concurrent_execution(self) -> None:
        """并发执行。"""
        call_count = 0

        async def agent_fn(messages: list[dict]) -> tuple[str, list[str]]:
            nonlocal call_count
            call_count += 1
            return "ok", []

        suite = BenchmarkSuite(
            name="concurrent",
            concurrency=5,
            cases=[BenchmarkCase(name=f"c{i}") for i in range(10)],
        )

        runner = BenchmarkRunner(agent_fn=agent_fn)
        report = await runner.run(suite)

        assert call_count == 10
        assert report.total_cases == 10

    @pytest.mark.asyncio
    async def test_runner_config_threshold(self) -> None:
        """通过阈值配置。"""

        async def agent_fn(messages: list[dict]) -> tuple[str, list[str]]:
            return "ok", []

        async def scorer(case: BenchmarkCase, output: str, tools: list[str]) -> dict:
            return {EvalDimension.ACCURACY: 0.5}

        config = RunnerConfig(pass_threshold=0.4)
        runner = BenchmarkRunner(agent_fn=agent_fn, scorer_fn=scorer, config=config)

        suite = BenchmarkSuite(name="threshold", cases=[BenchmarkCase(name="c")])
        report = await runner.run(suite)

        assert report.results[0].status == CaseStatus.PASSED

        # 阈值 0.6 则失败
        config2 = RunnerConfig(pass_threshold=0.6)
        runner2 = BenchmarkRunner(agent_fn=agent_fn, scorer_fn=scorer, config=config2)
        report2 = await runner2.run(suite)
        assert report2.results[0].status == CaseStatus.FAILED


# ── EvalDimension 测试 ──

class TestEvalDimension:
    def test_all_dimensions(self) -> None:
        assert len(EvalDimension) == 6

    def test_values(self) -> None:
        assert EvalDimension.ACCURACY.value == "accuracy"
        assert EvalDimension.HALLUCINATION.value == "hallucination"
