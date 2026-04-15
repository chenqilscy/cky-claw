"""工作流引擎综合测试。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.runner.result import RunResult
from ckyclaw_framework.tracing.span import SpanType
from ckyclaw_framework.workflow.config import WorkflowRunConfig
from ckyclaw_framework.workflow.engine import AgentNotFoundError, WorkflowEngine
from ckyclaw_framework.workflow.evaluator import UnsafeExpressionError, evaluate
from ckyclaw_framework.workflow.result import WorkflowStatus
from ckyclaw_framework.workflow.step import (
    AgentStep,
    BranchCondition,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    RetryConfig,
    StepIO,
    StepStatus,
    StepType,
)
from ckyclaw_framework.workflow.validator import (
    WorkflowValidationError,
    topological_sort,
    validate_workflow,
    validate_workflow_strict,
)
from ckyclaw_framework.workflow.workflow import Edge, Workflow

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_agent(name: str = "test-agent") -> Agent:
    return Agent(name=name, instructions="test")


def _make_resolver(*agents: Agent) -> AsyncMock:
    """创建 agent_resolver mock。"""
    agent_map = {a.name: a for a in agents}

    async def resolver(name: str) -> Agent:
        if name in agent_map:
            return agent_map[name]
        raise AgentNotFoundError(name)

    mock = AsyncMock(side_effect=resolver)
    return mock


def _make_run_result(output: Any = "ok") -> RunResult:
    return RunResult(output=output)


# ── Step 类型测试 ─────────────────────────────────────────────────────


class TestStepDefinitions:
    """步骤数据结构基础测试。"""

    def test_agent_step_type(self) -> None:
        step = AgentStep(id="s1", agent_name="a")
        assert step.type == StepType.AGENT

    def test_parallel_step_type(self) -> None:
        step = ParallelStep(id="p1")
        assert step.type == StepType.PARALLEL

    def test_conditional_step_type(self) -> None:
        step = ConditionalStep(id="c1")
        assert step.type == StepType.CONDITIONAL

    def test_loop_step_type(self) -> None:
        step = LoopStep(id="l1")
        assert step.type == StepType.LOOP

    def test_step_io(self) -> None:
        io = StepIO(
            input_keys={"local_in": "ctx_in"},
            output_keys={"local_out": "ctx_out"},
        )
        step = AgentStep(id="s1", agent_name="a", io=io)
        assert step.io.input_keys == {"local_in": "ctx_in"}

    def test_retry_config(self) -> None:
        retry = RetryConfig(max_retries=3, delay_seconds=0.5, backoff_multiplier=2.0)
        step = AgentStep(id="s1", agent_name="a", retry_config=retry)
        assert step.retry_config is not None
        assert step.retry_config.max_retries == 3


# ── Validator 测试 ────────────────────────────────────────────────────


class TestValidator:
    """DAG 验证器测试。"""

    def test_valid_linear_dag(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s2", agent_name="b")],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
        )
        errors = validate_workflow(wf)
        assert errors == []

    def test_duplicate_step_id(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s1", agent_name="b")],
            edges=[],
        )
        errors = validate_workflow(wf)
        assert any("重复" in e for e in errors)

    def test_edge_references_missing_step(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="missing")],
        )
        errors = validate_workflow(wf)
        assert any("不存在" in e for e in errors)

    def test_cycle_detection(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s2", agent_name="b")],
            edges=[
                Edge(id="e1", source_step_id="s1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s2", target_step_id="s1"),
            ],
        )
        errors = validate_workflow(wf)
        assert any("环" in e for e in errors)

    def test_topological_sort(self) -> None:
        wf = Workflow(
            name="test",
            steps=[
                AgentStep(id="s1", agent_name="a"),
                AgentStep(id="s2", agent_name="b"),
                AgentStep(id="s3", agent_name="c"),
            ],
            edges=[
                Edge(id="e1", source_step_id="s1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s1", target_step_id="s3"),
                Edge(id="e3", source_step_id="s2", target_step_id="s3"),
            ],
        )
        order = topological_sort(wf)
        assert order.index("s1") < order.index("s2")
        assert order.index("s2") < order.index("s3")

    def test_topological_sort_cycle_raises(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s2", agent_name="b")],
            edges=[
                Edge(id="e1", source_step_id="s1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s2", target_step_id="s1"),
            ],
        )
        with pytest.raises(WorkflowValidationError, match="环"):
            topological_sort(wf)

    def test_validate_strict_raises(self) -> None:
        wf = Workflow(
            name="test",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s1", agent_name="b")],
            edges=[],
        )
        with pytest.raises(WorkflowValidationError):
            validate_workflow_strict(wf)

    def test_nesting_parallel_in_parallel(self) -> None:
        inner = ParallelStep(id="inner")
        outer = ParallelStep(id="outer", sub_steps=[inner])  # type: ignore[arg-type]
        wf = Workflow(name="test", steps=[outer])
        errors = validate_workflow(wf)
        assert any("不允许嵌套" in e for e in errors)

    def test_nesting_loop_in_loop(self) -> None:
        inner = LoopStep(id="inner", condition="True")
        outer = LoopStep(id="outer", body_steps=[inner], condition="True")  # type: ignore[arg-type]
        wf = Workflow(name="test", steps=[outer])
        errors = validate_workflow(wf)
        assert any("不允许嵌套" in e for e in errors)

    def test_output_key_conflict_in_parallel(self) -> None:
        s1 = AgentStep(id="s1", agent_name="a", io=StepIO(output_keys={"out": "shared_key"}))
        s2 = AgentStep(id="s2", agent_name="b", io=StepIO(output_keys={"out": "shared_key"}))
        pstep = ParallelStep(id="p1", sub_steps=[s1, s2])
        wf = Workflow(name="test", steps=[pstep])
        errors = validate_workflow(wf)
        assert any("output_key" in e for e in errors)

    def test_conditional_target_missing(self) -> None:
        cond = ConditionalStep(
            id="c1",
            branches=[BranchCondition(label="yes", condition="True", target_step_id="missing")],
        )
        wf = Workflow(name="test", steps=[cond])
        errors = validate_workflow(wf)
        assert any("目标" in e and "不存在" in e for e in errors)


# ── Evaluator 测试 ────────────────────────────────────────────────────


class TestEvaluator:
    """安全表达式求值器测试。"""

    def test_simple_comparison(self) -> None:
        assert evaluate("x > 5", {"x": 10}) is True

    def test_boolean_and(self) -> None:
        assert evaluate("x > 0 and y > 0", {"x": 1, "y": 2}) is True

    def test_boolean_or(self) -> None:
        assert evaluate("x > 0 or y > 0", {"x": 0, "y": 1}) is True

    def test_not(self) -> None:
        assert evaluate("not x", {"x": False}) is True

    def test_equality(self) -> None:
        assert evaluate("status == 'approved'", {"status": "approved"}) is True

    def test_in_operator(self) -> None:
        assert evaluate("'a' in items", {"items": ["a", "b"]}) is True

    def test_dot_path(self) -> None:
        assert evaluate("result.score > 80", {"result": {"score": 90}}) is True

    def test_nested_dot_path(self) -> None:
        ctx = {"a": {"b": {"c": 42}}}
        assert evaluate("a.b.c == 42", ctx) is True

    def test_none_reference(self) -> None:
        assert evaluate("x is None", {"x": None}) is True

    def test_constant_string(self) -> None:
        assert evaluate("'hello' == 'hello'", {}) is True

    def test_missing_key_is_none(self) -> None:
        assert evaluate("missing is None", {}) is True

    def test_unsafe_function_call(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("__import__('os').system('rm -rf /')", {})

    def test_unsafe_lambda(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("(lambda: 1)()", {})

    def test_syntax_error(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="语法错误"):
            evaluate("if True:", {})

    def test_list_literal(self) -> None:
        result = evaluate("[1, 2, 3]", {})
        assert result == [1, 2, 3]

    def test_complex_condition(self) -> None:
        ctx = {"score": 85, "passed": True}
        assert evaluate("score >= 80 and passed == True", ctx) is True

    def test_unary_minus(self) -> None:
        assert evaluate("-1 == -1", {}) is True


# ── Engine: 线性 DAG 测试 ─────────────────────────────────────────────


class TestLinearDAG:
    """线性 DAG 执行测试。"""

    @pytest.mark.asyncio
    async def test_single_step(self) -> None:
        agent = _make_agent("agent-a")
        resolver = _make_resolver(agent)

        wf = Workflow(
            name="single",
            steps=[AgentStep(id="s1", agent_name="agent-a", prompt_template="hello")],
            edges=[],
        )

        with _patch_runner("output-1"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert "s1" in result.step_results
        assert result.step_results["s1"].status == StepStatus.COMPLETED
        resolver.assert_called_once_with("agent-a")

    @pytest.mark.asyncio
    async def test_linear_two_steps(self) -> None:
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        wf = Workflow(
            name="linear",
            steps=[
                AgentStep(id="s1", agent_name="a"),
                AgentStep(id="s2", agent_name="b"),
            ],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
        )

        with _patch_runner("result"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 2

    @pytest.mark.asyncio
    async def test_context_flow(self) -> None:
        """验证 context 在步骤间传递。"""
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        wf = Workflow(
            name="ctx-flow",
            steps=[
                AgentStep(
                    id="s1",
                    agent_name="a",
                    io=StepIO(output_keys={"result": "step1_output"}),
                ),
                AgentStep(
                    id="s2",
                    agent_name="b",
                    io=StepIO(input_keys={"data": "step1_output"}),
                ),
            ],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
        )

        call_count = 0

        async def mock_run(agent, input, *, config=None, max_turns=10, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return RunResult(output={"result": "from-step-1"})
            return RunResult(output="done")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=mock_run)
        try:
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.COMPLETED
        assert result.context.get("step1_output") == "from-step-1"

    @pytest.mark.asyncio
    async def test_initial_context(self) -> None:
        """验证初始 context 传入。"""
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="init-ctx",
            steps=[AgentStep(id="s1", agent_name="a", prompt_template="Input: {{user_query}}")],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(
                wf,
                context={"user_query": "hello world"},
                agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED


# ── Engine: 并行执行测试 ──────────────────────────────────────────────


class TestParallelExecution:
    """并行步骤执行测试。"""

    @pytest.mark.asyncio
    async def test_parallel_step(self) -> None:
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        sub1 = AgentStep(id="sub1", agent_name="a", io=StepIO(output_keys={"out": "out1"}))
        sub2 = AgentStep(id="sub2", agent_name="b", io=StepIO(output_keys={"out": "out2"}))
        pstep = ParallelStep(id="p1", sub_steps=[sub1, sub2])

        wf = Workflow(name="parallel", steps=[pstep], edges=[])

        with _patch_runner("parallel-result"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert "sub1" in result.step_results
        assert "sub2" in result.step_results

    @pytest.mark.asyncio
    async def test_parallel_fail_fast(self) -> None:
        """fail_fast 模式下一个子步骤失败导致整个 ParallelStep 失败。"""
        agent_a = _make_agent("a")
        resolver = _make_resolver(agent_a)

        sub1 = AgentStep(id="sub1", agent_name="a")
        sub2 = AgentStep(id="sub2", agent_name="missing-agent")
        pstep = ParallelStep(id="p1", sub_steps=[sub1, sub2], fail_policy="fail_fast")

        wf = Workflow(name="parallel-fail", steps=[pstep], edges=[])

        async def mixed_run(agent, input, *, config=None, max_turns=10, **kw):
            return RunResult(output="ok")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=mixed_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=True),
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_parallel_all_settled(self) -> None:
        """all_settled 模式等待所有子步骤完成。"""
        resolver = _make_resolver(_make_agent("a"))

        sub1 = AgentStep(id="sub1", agent_name="a")
        sub2 = AgentStep(id="sub2", agent_name="missing-agent")
        pstep = ParallelStep(id="p1", sub_steps=[sub1, sub2], fail_policy="all_settled")

        wf = Workflow(name="parallel-settled", steps=[pstep], edges=[])

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=True),
            )

        assert result.status == WorkflowStatus.FAILED


# ── Engine: 条件分支测试 ──────────────────────────────────────────────


class TestConditionalExecution:
    """条件分支执行测试。"""

    @pytest.mark.asyncio
    async def test_conditional_true_branch(self) -> None:
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        cond = ConditionalStep(
            id="c1",
            branches=[
                BranchCondition(label="high", condition="score > 80", target_step_id="s_high"),
            ],
            default_step_id="s_low",
        )
        s_high = AgentStep(id="s_high", agent_name="a")
        s_low = AgentStep(id="s_low", agent_name="b")

        wf = Workflow(
            name="cond",
            steps=[cond, s_high, s_low],
            edges=[
                Edge(id="e1", source_step_id="c1", target_step_id="s_high"),
                Edge(id="e2", source_step_id="c1", target_step_id="s_low"),
            ],
        )

        with _patch_runner("high-result"):
            result = await WorkflowEngine.run(
                wf,
                context={"score": 90},
                agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED
        assert "s_high" in result.step_results
        # s_low 被跳过
        assert "s_low" not in result.step_results or result.step_results.get("s_low", MagicMock()).status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_conditional_default_branch(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        cond = ConditionalStep(
            id="c1",
            branches=[
                BranchCondition(label="high", condition="score > 80", target_step_id="s_high"),
            ],
            default_step_id="s_default",
        )
        s_high = AgentStep(id="s_high", agent_name="a")
        s_default = AgentStep(id="s_default", agent_name="a")

        wf = Workflow(
            name="cond-default",
            steps=[cond, s_high, s_default],
            edges=[
                Edge(id="e1", source_step_id="c1", target_step_id="s_high"),
                Edge(id="e2", source_step_id="c1", target_step_id="s_default"),
            ],
        )

        with _patch_runner("default-result"):
            result = await WorkflowEngine.run(
                wf,
                context={"score": 50},
                agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED
        assert "s_default" in result.step_results


# ── Engine: 循环测试 ──────────────────────────────────────────────────


class TestLoopExecution:
    """循环步骤测试。"""

    @pytest.mark.asyncio
    async def test_loop_basic(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        body = AgentStep(id="body1", agent_name="a", io=StepIO(output_keys={"out": "count"}))
        loop = LoopStep(
            id="l1",
            body_steps=[body],
            condition="count < 3",
            max_iterations=5,
            iteration_output_key="loop_results",
        )

        wf = Workflow(name="loop", steps=[loop], edges=[])

        call_count = 0

        async def counting_run(agent, input, *, config=None, max_turns=10, **kw):
            nonlocal call_count
            call_count += 1
            return RunResult(output={"out": call_count})

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=counting_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                context={"count": 0},
                agent_resolver=resolver,
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.COMPLETED
        assert "loop_results" in result.context
        assert isinstance(result.context["loop_results"], list)

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self) -> None:
        """max_iterations 保护无限循环。"""
        resolver = _make_resolver(_make_agent("a"))

        body = AgentStep(id="body1", agent_name="a")
        loop = LoopStep(
            id="l1",
            body_steps=[body],
            condition="True",
            max_iterations=3,
        )

        wf = Workflow(name="loop-max", steps=[loop], edges=[])

        with _patch_runner("iter"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_loop_while_semantics(self) -> None:
        """while 语义：条件为 False 时不执行 body。"""
        resolver = _make_resolver(_make_agent("a"))

        body = AgentStep(id="body1", agent_name="a")
        loop = LoopStep(
            id="l1",
            body_steps=[body],
            condition="should_loop == True",
            max_iterations=10,
        )

        wf = Workflow(name="loop-while", steps=[loop], edges=[])

        with _patch_runner("nope"):
            result = await WorkflowEngine.run(
                wf,
                context={"should_loop": False},
                agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED
        # body 不应被执行
        assert "body1" not in result.step_results


# ── Engine: 错误处理测试 ──────────────────────────────────────────────


class TestErrorHandling:
    """错误和异常处理测试。"""

    @pytest.mark.asyncio
    async def test_agent_not_found(self) -> None:
        resolver = _make_resolver()  # 无 agent

        wf = Workflow(
            name="not-found",
            steps=[AgentStep(id="s1", agent_name="ghost")],
            edges=[],
        )

        result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.FAILED
        assert "s1" in result.step_results
        assert result.step_results["s1"].status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_cancel_event(self) -> None:
        resolver = _make_resolver(_make_agent("a"))
        cancel = asyncio.Event()
        cancel.set()  # 立即取消

        wf = Workflow(
            name="cancel",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        result = await WorkflowEngine.run(
            wf,
            agent_resolver=resolver,
            cancel_event=cancel,
        )

        assert result.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        agent = _make_agent("a")
        resolver = _make_resolver(agent)

        retry = RetryConfig(max_retries=2, delay_seconds=0.01, backoff_multiplier=1.0)
        step = AgentStep(id="s1", agent_name="a", retry_config=retry)

        wf = Workflow(name="retry", steps=[step], edges=[])

        call_count = 0

        async def flaky_run(agent, input, *, config=None, max_turns=10, **kw):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return RunResult(output="success")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=flaky_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.COMPLETED
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fail_fast_stops_execution(self) -> None:
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        wf = Workflow(
            name="fail-fast",
            steps=[
                AgentStep(id="s1", agent_name="a"),
                AgentStep(id="s2", agent_name="b"),
            ],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
        )

        async def fail_run(agent, input, *, config=None, max_turns=10, **kw):
            raise RuntimeError("boom")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=fail_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=True),
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.FAILED
        # s2 不应执行
        assert "s2" not in result.step_results

    @pytest.mark.asyncio
    async def test_step_timeout(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        step = AgentStep(id="s1", agent_name="a", timeout=0.01)
        wf = Workflow(name="timeout", steps=[step], edges=[])

        async def slow_run(agent, input, *, config=None, max_turns=10, **kw):
            await asyncio.sleep(10)
            return RunResult(output="never")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=slow_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.step_results["s1"].status == StepStatus.FAILED
        assert "超时" in (result.step_results["s1"].error or "")


# ── Engine: Tracing 测试 ──────────────────────────────────────────────


class TestTracing:
    """链路追踪集成测试。"""

    @pytest.mark.asyncio
    async def test_trace_created(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="traced",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(tracing_enabled=True),
            )

        assert result.trace is not None
        assert result.trace.workflow_name == "traced"
        assert len(result.trace.spans) > 0

    @pytest.mark.asyncio
    async def test_trace_disabled(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="no-trace",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(tracing_enabled=False),
            )

        assert result.trace is None

    @pytest.mark.asyncio
    async def test_span_type_workflow_step(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="span-type",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(tracing_enabled=True),
            )

        assert result.trace is not None
        wf_spans = [s for s in result.trace.spans if s.type == SpanType.WORKFLOW_STEP]
        assert len(wf_spans) >= 1

    @pytest.mark.asyncio
    async def test_trace_processor_called(self) -> None:
        resolver = _make_resolver(_make_agent("a"))
        processor = AsyncMock()
        processor.on_trace_start = AsyncMock()
        processor.on_trace_end = AsyncMock()
        processor.on_span_start = AsyncMock()
        processor.on_span_end = AsyncMock()

        wf = Workflow(
            name="processor",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("ok"):
            await WorkflowEngine.run(
                wf,
                agent_resolver=resolver,
                config=WorkflowRunConfig(tracing_enabled=True),
                trace_processors=[processor],
            )

        processor.on_trace_start.assert_called_once()
        processor.on_trace_end.assert_called_once()
        assert processor.on_span_start.call_count >= 1


# ── Engine: 复杂 DAG 测试 ────────────────────────────────────────────


class TestComplexDAG:
    """复杂 DAG 拓扑测试。"""

    @pytest.mark.asyncio
    async def test_diamond_dag(self) -> None:
        """钻石型 DAG: s1 → {s2, s3} → s4"""
        resolver = _make_resolver(
            _make_agent("a"), _make_agent("b"), _make_agent("c"), _make_agent("d"),
        )

        wf = Workflow(
            name="diamond",
            steps=[
                AgentStep(id="s1", agent_name="a"),
                AgentStep(id="s2", agent_name="b"),
                AgentStep(id="s3", agent_name="c"),
                AgentStep(id="s4", agent_name="d"),
            ],
            edges=[
                Edge(id="e1", source_step_id="s1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s1", target_step_id="s3"),
                Edge(id="e3", source_step_id="s2", target_step_id="s4"),
                Edge(id="e4", source_step_id="s3", target_step_id="s4"),
            ],
        )

        with _patch_runner("diamond-ok"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 4

    @pytest.mark.asyncio
    async def test_independent_steps_parallel(self) -> None:
        """无边的独立步骤应并行执行。"""
        resolver = _make_resolver(_make_agent("a"), _make_agent("b"))

        wf = Workflow(
            name="independent",
            steps=[
                AgentStep(id="s1", agent_name="a"),
                AgentStep(id="s2", agent_name="b"),
            ],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 2


# ── Template Rendering 测试 ──────────────────────────────────────────


class TestTemplateRendering:
    """Prompt 模板渲染测试。"""

    @pytest.mark.asyncio
    async def test_template_substitution(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="template",
            steps=[
                AgentStep(
                    id="s1",
                    agent_name="a",
                    prompt_template="Analyze: {{user_input}}",
                    io=StepIO(input_keys={"user_input": "query"}),
                ),
            ],
            edges=[],
        )

        captured_input = []

        async def capture_run(agent, input, *, config=None, max_turns=10, **kw):
            captured_input.append(input)
            return RunResult(output="analyzed")

        import ckyclaw_framework.workflow.engine as engine_mod
        original_run = engine_mod.Runner.run
        engine_mod.Runner.run = AsyncMock(side_effect=capture_run)
        try:
            result = await WorkflowEngine.run(
                wf,
                context={"query": "What is CkyClaw?"},
                agent_resolver=resolver,
            )
        finally:
            engine_mod.Runner.run = original_run

        assert result.status == WorkflowStatus.COMPLETED
        assert captured_input[0] == "Analyze: What is CkyClaw?"


# ── AgentNotFoundError 测试 ──────────────────────────────────────────


class TestAgentNotFoundError:
    """AgentNotFoundError 测试。"""

    def test_error_message(self) -> None:
        err = AgentNotFoundError("ghost")
        assert err.agent_name == "ghost"
        assert "ghost" in str(err)

    @pytest.mark.asyncio
    async def test_resolver_raises_not_found(self) -> None:
        resolver = _make_resolver()  # 空

        wf = Workflow(
            name="nf",
            steps=[AgentStep(id="s1", agent_name="nonexistent")],
            edges=[],
        )

        result = await WorkflowEngine.run(wf, agent_resolver=resolver)
        assert result.status == WorkflowStatus.FAILED
        assert result.step_results["s1"].status == StepStatus.FAILED
        assert "not found" in (result.step_results["s1"].error or "").lower()


# ── Workflow Validation Error 测试 ────────────────────────────────────


class TestWorkflowValidationError:
    """WorkflowValidationError 测试。"""

    def test_error_has_errors_list(self) -> None:
        err = WorkflowValidationError(["err1", "err2"])
        assert len(err.errors) == 2
        assert "err1" in str(err)

    @pytest.mark.asyncio
    async def test_invalid_workflow_rejected(self) -> None:
        """无效工作流（环）在 run 时被拒绝。"""
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="cycle",
            steps=[AgentStep(id="s1", agent_name="a"), AgentStep(id="s2", agent_name="a")],
            edges=[
                Edge(id="e1", source_step_id="s1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s2", target_step_id="s1"),
            ],
        )

        result = await WorkflowEngine.run(wf, agent_resolver=resolver)
        assert result.status == WorkflowStatus.FAILED


# ── WorkflowResult 测试 ──────────────────────────────────────────────


class TestWorkflowResult:
    """WorkflowResult 属性测试。"""

    @pytest.mark.asyncio
    async def test_result_has_duration(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="dur",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("ok"):
            result = await WorkflowEngine.run(wf, agent_resolver=resolver)

        assert result.duration_ms is not None
        assert result.duration_ms >= 0
        assert result.started_at is not None
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_result_context_preserved(self) -> None:
        resolver = _make_resolver(_make_agent("a"))

        wf = Workflow(
            name="ctx",
            steps=[AgentStep(id="s1", agent_name="a")],
            edges=[],
        )

        with _patch_runner("hello"):
            result = await WorkflowEngine.run(
                wf,
                context={"initial": "data"},
                agent_resolver=resolver,
            )

        assert result.context.get("initial") == "data"


# ── 辅助函数 ─────────────────────────────────────────────────────────


class _patch_runner:  # noqa: N801
    """Mock Runner.run 返回固定 output 的上下文管理器。"""

    def __init__(self, output: Any = "ok") -> None:
        self.output = output
        self._original = None

    def __enter__(self):
        import ckyclaw_framework.workflow.engine as engine_mod

        self._original = engine_mod.Runner.run

        async def mock_run(agent, input, *, config=None, max_turns=10, **kw):
            return RunResult(output=self.output)

        engine_mod.Runner.run = AsyncMock(side_effect=mock_run)
        return self

    def __exit__(self, *args):
        import ckyclaw_framework.workflow.engine as engine_mod
        engine_mod.Runner.run = self._original
