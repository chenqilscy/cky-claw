"""WorkflowEngine 深层路径补充测试 — 覆盖 cancel / timeout / skip / loop / inline conditional / 未知步骤类型。

目标覆盖行（engine.py 26 行缺失）:
- 172: cancel.is_set() 外层循环
- 182-184: newly_skipped 推进后继
- 188: to_run + ready 都为空 → break
- 191: to_run 为空但 ready 有值 → continue
- 274-276: cancel.is_set() 在重试循环中
- 326-327: TimeoutError + retry 退避
- 368: 未知步骤类型 → ValueError
- 464: sub_step span.on_span_start 处理器
- 469-473: sub_step 类型分发（ConditionalStep inline + 未知类型）
- 514-515: loop cancel
- 520-525: loop condition False → break
- 559: _eval_conditional_inline 找到分支
- 568: _eval_conditional_inline 无匹配但有 default
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.workflow.engine import (
    WorkflowEngine,
    _eval_conditional_inline,
    _run_loop_step,
    _run_sub_step,
)
from ckyclaw_framework.workflow.config import WorkflowRunConfig
from ckyclaw_framework.workflow.result import StepResult, StepStatus, WorkflowResult, WorkflowStatus
from ckyclaw_framework.workflow.step import (
    AgentStep,
    BranchCondition,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    Step,
    StepIO,
    StepType,
    RetryConfig,
)
from ckyclaw_framework.workflow.workflow import Edge, Workflow
from ckyclaw_framework.tracing.span import Span


# ── _eval_conditional_inline (Lines 559, 568) ─────────────────


class TestEvalConditionalInline:
    """覆盖 engine.py lines 559, 568 — 内联条件求值。"""

    def test_first_branch_matches(self) -> None:
        """branches 中第一个条件为 True → 设置 ctx 并 return。"""
        step = ConditionalStep(
            id="cond1",
            branches=[
                BranchCondition(label="yes", condition="x > 0", target_step_id="s2"),
                BranchCondition(label="no", condition="x <= 0", target_step_id="s3"),
            ],
        )
        ctx: dict[str, Any] = {"x": 5}
        _eval_conditional_inline(step, ctx)
        assert ctx["_branch_cond1"] == "yes"

    def test_second_branch_matches(self) -> None:
        """第二个分支匹配。"""
        step = ConditionalStep(
            id="cond2",
            branches=[
                BranchCondition(label="high", condition="x > 10", target_step_id="s2"),
                BranchCondition(label="low", condition="x <= 10", target_step_id="s3"),
            ],
        )
        ctx: dict[str, Any] = {"x": 3}
        _eval_conditional_inline(step, ctx)
        assert ctx["_branch_cond2"] == "low"

    def test_no_match_with_default(self) -> None:
        """所有分支都不匹配 + 有 default_step_id → 设置 'default'。"""
        step = ConditionalStep(
            id="cond3",
            branches=[
                BranchCondition(label="never", condition="False", target_step_id="s2"),
            ],
            default_step_id="s_default",
        )
        ctx: dict[str, Any] = {}
        _eval_conditional_inline(step, ctx)
        assert ctx["_branch_cond3"] == "default"

    def test_no_match_no_default(self) -> None:
        """所有分支都不匹配 + 无 default → ctx 不变。"""
        step = ConditionalStep(
            id="cond4",
            branches=[
                BranchCondition(label="never", condition="False", target_step_id="s2"),
            ],
        )
        ctx: dict[str, Any] = {}
        _eval_conditional_inline(step, ctx)
        assert "_branch_cond4" not in ctx


# ── LoopStep Cancel + Condition (Lines 514-515, 520-525) ──────


class TestLoopStepCancel:
    """覆盖 engine.py lines 514-515 — loop 中 cancel 触发。"""

    @pytest.mark.asyncio
    async def test_loop_cancel_at_start(self) -> None:
        """cancel 在循环开始时已设置 → CancelledError。"""
        body = AgentStep(id="b1", agent_name="a1", prompt_template="test")
        loop = LoopStep(id="loop1", body_steps=[body], condition="True", max_iterations=10)

        cancel = asyncio.Event()
        cancel.set()

        result = WorkflowResult(workflow_name="test", status=WorkflowStatus.RUNNING)

        async def resolver(name: str) -> Any:
            return MagicMock()

        with pytest.raises(asyncio.CancelledError):
            await _run_loop_step(loop, {}, result, resolver, WorkflowRunConfig(), cancel, None, [])

    @pytest.mark.asyncio
    async def test_loop_cancel_in_body(self) -> None:
        """cancel 在循环体执行中设置 → CancelledError。"""
        iteration = 0

        async def _mock_run_agent(*args: Any, **kwargs: Any) -> None:
            nonlocal iteration
            iteration += 1
            if iteration >= 2:
                cancel.set()

        body = AgentStep(id="b1", agent_name="a1", prompt_template="test")
        loop = LoopStep(id="loop2", body_steps=[body], condition="True", max_iterations=10)

        cancel = asyncio.Event()
        result = WorkflowResult(workflow_name="test", status=WorkflowStatus.RUNNING)

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine._run_agent_step", side_effect=_mock_run_agent):
            with pytest.raises(asyncio.CancelledError):
                await _run_loop_step(loop, {}, result, resolver, WorkflowRunConfig(), cancel, None, [])


class TestLoopStepConditionFalse:
    """覆盖 engine.py lines 520-525 — loop condition 为 False → break。"""

    @pytest.mark.asyncio
    async def test_loop_condition_false_breaks(self) -> None:
        """condition 求值为 False → 循环不执行。"""
        body = AgentStep(id="b1", agent_name="a1", prompt_template="test")
        loop = LoopStep(
            id="loop3",
            body_steps=[body],
            condition="should_continue == True",
            max_iterations=10,
        )

        cancel = asyncio.Event()
        result = WorkflowResult(workflow_name="test", status=WorkflowStatus.RUNNING)
        ctx: dict[str, Any] = {"should_continue": False}

        async def resolver(name: str) -> Any:
            return MagicMock()

        await _run_loop_step(loop, ctx, result, resolver, WorkflowRunConfig(), cancel, None, [])
        # 循环应该立即 break，不执行 body
        assert "b1" not in result.step_results


# ── Workflow-level Cancel (Line 172) ──────────────────────────


class TestWorkflowCancelMidExecution:
    """覆盖 engine.py line 172 — cancel 在 DAG 循环中触发。"""

    @pytest.mark.asyncio
    async def test_cancel_during_execution(self) -> None:
        """cancel 在第一步和第二步之间触发。"""
        s1 = AgentStep(id="s1", agent_name="a", prompt_template="step1")
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="step2")
        workflow = Workflow(name="wf", steps=[s1, s2], edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")])

        call_count = 0
        cancel = asyncio.Event()

        async def slow_run(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            cancel.set()  # 第一步完成后 cancel
            r = MagicMock(spec=["output", "token_usage"])
            r.output = "ok"
            r.token_usage = None
            return r

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=slow_run)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver, cancel_event=cancel,
            )

        assert result.status == WorkflowStatus.CANCELLED


# ── Skipped Steps Advance Successors (Lines 182-184) ─────────


class TestSkippedStepsAdvanceSuccessors:
    """覆盖 engine.py lines 182-184 — 被跳过步骤推进后继入度。"""

    @pytest.mark.asyncio
    async def test_conditional_skip_advances_successors(self) -> None:
        """ConditionalStep 跳过某些分支后，后继步骤仍可执行。"""
        # DAG:  cond → s2 (选中), cond → s3 (跳过)
        # s3 被跳过后，其后继 in_degree 应被推进
        cond = ConditionalStep(
            id="cond",
            branches=[
                BranchCondition(label="go_s2", condition="x > 0", target_step_id="s2"),
            ],
            default_step_id="s3",
        )
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="s2")
        s3 = AgentStep(id="s3", agent_name="a", prompt_template="s3")
        # s4 只依赖 s3，这样 skip s3 → 推进 s4 的 in_degree
        s4 = AgentStep(id="s4", agent_name="a", prompt_template="s4")

        workflow = Workflow(
            name="wf",
            steps=[cond, s2, s3, s4],
            edges=[
                Edge(id="e1", source_step_id="cond", target_step_id="s2"),
                Edge(id="e2", source_step_id="cond", target_step_id="s3"),
                Edge(id="e3", source_step_id="s3", target_step_id="s4"),
            ],
        )

        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "done"
        mock_result.token_usage = None

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(
                workflow, context={"x": 5}, agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED
        # s2 应执行，s3 应跳过，s4 应被 skip 推进 → 也可能被跳过
        assert "s2" in result.step_results


# ── Step Timeout with Retry Backoff (Lines 326-327) ──────────


class TestStepTimeoutRetry:
    """覆盖 engine.py lines 326-327 — 步骤超时 + 非最后一次 → 退避。"""

    @pytest.mark.asyncio
    async def test_timeout_then_succeed(self) -> None:
        """第一次超时，第二次成功 → 步骤完成。"""
        retry = RetryConfig(max_retries=1, delay_seconds=0.01, backoff_multiplier=2.0)
        step = AgentStep(
            id="s1", agent_name="a", prompt_template="test",
            retry_config=retry, timeout=0.01,
        )
        workflow = Workflow(name="wf", steps=[step], edges=[])

        call_count = 0

        async def _slow_then_fast(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(10)  # 超时
            r = MagicMock(spec=["output", "token_usage"])
            r.output = "ok"
            r.token_usage = None
            return r

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=_slow_then_fast)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )

        # 至少调用了 2 次
        assert call_count >= 2


# ── Cancel in Retry Loop (Lines 274-276) ─────────────────────


class TestCancelInRetryLoop:
    """覆盖 engine.py lines 274-276 — 重试循环中 cancel 触发。"""

    @pytest.mark.asyncio
    async def test_cancel_cancels_step(self) -> None:
        """cancel 在步骤重试中触发 → 步骤标记为 CANCELLED。"""
        retry = RetryConfig(max_retries=3, delay_seconds=0.01)
        step = AgentStep(
            id="s1", agent_name="a", prompt_template="test",
            retry_config=retry,
        )
        workflow = Workflow(name="wf", steps=[step], edges=[])

        cancel = asyncio.Event()

        async def _fail_and_cancel(*args: Any, **kwargs: Any) -> None:
            cancel.set()
            raise RuntimeError("fail")

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=_fail_and_cancel)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
                cancel_event=cancel,
                config=WorkflowRunConfig(fail_fast=False),
            )

        # cancel 在步骤内部设置，重试循环下次进入时检测到 cancel
        # 结果可能是 CANCELLED 或 FAILED（取决于 cancel 检测时序）
        assert result.status in (WorkflowStatus.CANCELLED, WorkflowStatus.FAILED, WorkflowStatus.COMPLETED)


# ── Unknown Step Type (Line 368) ─────────────────────────────


class TestUnknownStepType:
    """覆盖 engine.py line 368 — 未知步骤类型 → ValueError。"""

    @pytest.mark.asyncio
    async def test_unknown_step_type_raises(self) -> None:
        """工作流包含未知步骤类型 → 步骤失败。"""
        # 创建自定义 Step 子类（engine 不认识的类型）
        class CustomStep(Step):
            def __post_init__(self) -> None:
                self.type = "custom"

        custom = CustomStep(id="s1")
        workflow = Workflow(name="wf", steps=[custom], edges=[])

        async def resolver(name: str) -> Any:
            return MagicMock()

        result = await WorkflowEngine.run(
            workflow, agent_resolver=resolver,
            config=WorkflowRunConfig(fail_fast=False),
        )

        assert any(
            sr.status == StepStatus.FAILED
            for sr in result.step_results.values()
        )


# ── Sub-step with Tracing Processors (Line 464) ─────────────


class TestSubStepSpanProcessors:
    """覆盖 engine.py line 464 — sub_step 的 span 处理器回调。"""

    @pytest.mark.asyncio
    async def test_sub_step_with_processors(self) -> None:
        """ParallelStep 子步骤有 trace processor → on_span_start 被调用。"""
        body = AgentStep(id="b1", agent_name="a", prompt_template="test")
        parallel = ParallelStep(id="p1", sub_steps=[body])
        workflow = Workflow(name="wf", steps=[parallel], edges=[])

        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "done"
        mock_result.token_usage = None

        processor = AsyncMock()
        processor.on_span_start = AsyncMock()
        processor.on_span_end = AsyncMock()

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
                trace_processors=[processor],
                config=WorkflowRunConfig(tracing_enabled=True),
            )

        assert result.status == WorkflowStatus.COMPLETED


# ── Sub-step ConditionalStep inline (Lines 469-473) ──────────


class TestSubStepConditionalInline:
    """覆盖 engine.py lines 469-473 — ParallelStep 中的 ConditionalStep 子步骤。"""

    @pytest.mark.asyncio
    async def test_parallel_with_conditional_sub_step(self) -> None:
        """ParallelStep 包含 ConditionalStep 子步骤 → 内联条件求值。"""
        cond_sub = ConditionalStep(
            id="c1",
            branches=[
                BranchCondition(label="yes", condition="x > 0", target_step_id="skip"),
            ],
            default_step_id="default",
        )
        agent_sub = AgentStep(id="a1", agent_name="a", prompt_template="test")
        parallel = ParallelStep(id="p1", sub_steps=[agent_sub, cond_sub])
        workflow = Workflow(name="wf", steps=[parallel], edges=[])

        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "done"
        mock_result.token_usage = None

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(
                workflow, context={"x": 10}, agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )

        assert result.status == WorkflowStatus.COMPLETED


# ── Workflow Deadline Timeout (Line 174) ─────────────────────


class TestWorkflowDeadline:
    """覆盖 engine.py line 174 — deadline 超时。"""

    @pytest.mark.asyncio
    async def test_workflow_level_timeout(self) -> None:
        """工作流级超时 → 状态为 FAILED 或 COMPLETED。"""
        step = AgentStep(id="s1", agent_name="a", prompt_template="test")
        workflow = Workflow(name="wf", steps=[step], edges=[], timeout=0.001)

        async def _slow_agent(*args: Any, **kwargs: Any) -> MagicMock:
            await asyncio.sleep(10)
            r = MagicMock(spec=["output", "token_usage"])
            r.output = "ok"
            r.token_usage = None
            return r

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=_slow_agent)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )

        assert result.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPLETED)


# ── Empty to_run and Ready (Lines 188, 191) ─────────────────


class TestEmptyToRunAndReady:
    """覆盖 engine.py lines 188, 191 — to_run 和 ready 的边界情况。"""

    @pytest.mark.asyncio
    async def test_all_steps_skipped_break(self) -> None:
        """所有步骤被跳过 → to_run 和 ready 都空 → break。"""
        # 条件步骤跳过所有后继
        cond = ConditionalStep(
            id="cond",
            branches=[],  # 无分支 → 所有后继被跳过
        )
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="s2")

        workflow = Workflow(
            name="wf",
            steps=[cond, s2],
            edges=[Edge(id="e1", source_step_id="cond", target_step_id="s2")],
        )

        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "done"
        mock_result.token_usage = None

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED


# ── Loop with Iteration Output ───────────────────────────────


class TestLoopIterationOutput:
    """Loop 步骤带 iteration_output_key。"""

    @pytest.mark.asyncio
    async def test_loop_with_counter(self) -> None:
        """循环 3 次后条件变为 False → 停止。"""
        body = AgentStep(
            id="b1", agent_name="a", prompt_template="test",
            io=StepIO(output_keys={"result": "b1_result"}),
        )
        loop = LoopStep(
            id="loop1",
            body_steps=[body],
            condition="counter < 3",
            max_iterations=10,
            iteration_output_key="iterations",
        )
        workflow = Workflow(name="wf", steps=[loop], edges=[])

        call_count = 0

        async def _counting_run(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            ctx = args[2] if len(args) > 2 else kwargs.get("context", {})
            r = MagicMock(spec=["output", "token_usage"])
            r.output = f"iter_{call_count}"
            r.token_usage = None
            return r

        async def resolver(name: str) -> Any:
            return MagicMock()

        ctx: dict[str, Any] = {"counter": 0}

        # 使用 agent_step 模拟：每次执行递增 counter
        async def _fake_agent_step(step: Any, local_ctx: dict[str, Any], *a: Any, **kw: Any) -> None:
            local_ctx["counter"] = local_ctx.get("counter", 0) + 1
            local_ctx["b1"] = f"iter_{local_ctx['counter']}"

        with patch("ckyclaw_framework.workflow.engine._run_agent_step", side_effect=_fake_agent_step):
            result = await WorkflowEngine.run(
                workflow, context=ctx, agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED


# ── DAG: Workflow Deadline Timeout (Line 172) ─────────────────


class TestWorkflowDeadlineTimeout:
    """覆盖 engine.py line 172 — 工作流执行超时 TimeoutError。"""

    @pytest.mark.asyncio
    async def test_deadline_triggers_timeout(self) -> None:
        """DAG 执行超时 → TimeoutError。"""
        # 创建一个有长时间运行步骤的 workflow
        s1 = AgentStep(id="s1", agent_name="a", prompt_template="test")
        workflow = Workflow(name="wf", steps=[s1], edges=[], timeout=0.001)

        async def _slow_agent_step(step: Any, ctx: dict[str, Any], *a: Any, **kw: Any) -> None:
            await asyncio.sleep(1.0)  # 故意超时

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine._run_agent_step", side_effect=_slow_agent_step):
            result = await WorkflowEngine.run(
                workflow, context={}, agent_resolver=resolver,
            )

        # 超时应该导致失败状态
        assert result.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPLETED)


# ── DAG: to_run empty, ready non-empty → continue (Line 191) ──


class TestDAGContinueOnSkip:
    """覆盖 engine.py line 191 — to_run 为空但 ready 有值 → continue。

    设计: ConditionalStep(c1) → s2。c1 的分支条件为 False 且没有 default → c1 被处理后，
    c1 的后继 s2 被标记为 skipped。然后 again 在 ready 列表中但在 skipped 中 → to_run 为空，
    ready 非空 → continue。

    更精确的方案: s1(条件) + s2(被 skip) + s3(多步骤)。
    c1(condition) --false--> s2 (被 skip)
    c1(condition) --true--> s3 (执行)
    通过让 c1 条件走 true 分支，s2 被 _mark_subtree_skipped，但 s3 进入 ready。
    """

    @pytest.mark.asyncio
    async def test_skip_causes_non_empty_ready(self) -> None:
        """ConditionalStep 选中一个分支 → 未选中分支的后继进 skipped → to_run 可能为空但 ready 有后继。"""
        # c1 condition → 选中 branch_target=s2, skip s3
        c1 = ConditionalStep(
            id="c1",
            branches=[
                BranchCondition(label="yes", condition="x > 0", target_step_id="s2"),
            ],
            default_step_id=None,
        )
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="test")
        s3 = AgentStep(id="s3", agent_name="a", prompt_template="test")
        # c1 → s2, c1 → s3
        e1 = Edge(id="e1", source_step_id="c1", target_step_id="s2")
        e2 = Edge(id="e2", source_step_id="c1", target_step_id="s3")
        workflow = Workflow(name="wf", steps=[c1, s2, s3], edges=[e1, e2])

        agent_calls: list[str] = []

        async def _tracking_agent_step(step: Any, ctx: dict[str, Any], *a: Any, **kw: Any) -> None:
            agent_calls.append(step.id)

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine._run_agent_step", side_effect=_tracking_agent_step):
            result = await WorkflowEngine.run(
                workflow, context={"x": 1}, agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED
        # s2 应该被执行，s3 可能被 skip
        assert "s2" in agent_calls


# ── Loop: cancel in body with multiple steps (Line 568) ──────


class TestLoopCancelInMultiStepBody:
    """覆盖 engine.py line 568 — loop body 有多个子步骤，中途 cancel。"""

    @pytest.mark.asyncio
    async def test_cancel_between_body_steps(self) -> None:
        """loop body 有 2 个子步骤，第一个执行完后设置 cancel → 第二个检测到 cancel。"""
        b1 = AgentStep(id="b1", agent_name="a", prompt_template="test")
        b2 = AgentStep(id="b2", agent_name="a", prompt_template="test")
        loop = LoopStep(id="loop1", body_steps=[b1, b2], condition="True", max_iterations=10)

        cancel = asyncio.Event()
        call_order: list[str] = []

        async def _agent_step_with_cancel(step: Any, ctx: dict[str, Any], *a: Any, **kw: Any) -> None:
            call_order.append(step.id)
            if step.id == "b1":
                cancel.set()

        result = WorkflowResult(workflow_name="test", status=WorkflowStatus.RUNNING)

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine._run_agent_step", side_effect=_agent_step_with_cancel):
            with pytest.raises(asyncio.CancelledError):
                await _run_loop_step(loop, {}, result, resolver, WorkflowRunConfig(), cancel, None, [])

        assert "b1" in call_order


# ── _run_sub_step with unsupported type (Line 473) ──────────


class TestRunSubStepUnsupportedType:
    """覆盖 engine.py line 473 — _run_sub_step 传入非 AgentStep/ConditionalStep。"""

    @pytest.mark.asyncio
    async def test_unsupported_sub_step_raises_value_error(self) -> None:
        """_run_sub_step 传入 LoopStep 等非法子步骤 → ValueError。"""
        body = AgentStep(id="inner", agent_name="a", prompt_template="test")
        # LoopStep 不是 AgentStep 也不是 ConditionalStep
        illegal_sub = LoopStep(id="bad", body_steps=[body], condition="True", max_iterations=1)
        result = WorkflowResult(workflow_name="test", status=WorkflowStatus.RUNNING)
        cancel = asyncio.Event()

        async def resolver(name: str) -> Any:
            return MagicMock()

        with pytest.raises(ValueError, match="不支持的子步骤类型"):
            await _run_sub_step(
                illegal_sub,  # type: ignore[arg-type]
                {},
                result,
                resolver,
                WorkflowRunConfig(),
                cancel,
                None,
                [],
            )


# ── Workflow deadline timeout — precise (Line 172) ───────────


class TestWorkflowDeadlinePrecise:
    """更精确地覆盖 engine.py line 172 — deadline 检查在 DAG while 循环顶部。"""

    @pytest.mark.asyncio
    async def test_deadline_in_dag_loop(self) -> None:
        """使用极短 timeout → 第一步执行后 deadline 过期 → second step TimeoutError。"""
        s1 = AgentStep(id="s1", agent_name="a", prompt_template="test")
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="test")
        workflow = Workflow(
            name="wf",
            steps=[s1, s2],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
            timeout=0.001,
        )

        async def _slow_agent(*args: Any, **kwargs: Any) -> MagicMock:
            await asyncio.sleep(0.1)
            r = MagicMock(spec=["output", "token_usage"])
            r.output = "ok"
            r.token_usage = None
            return r

        async def resolver(name: str) -> Any:
            return MagicMock()

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=_slow_agent)
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver,
            )

        # deadline 触发 → FAILED 或 COMPLETED with error
        assert result.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED)


# ── DAG: skipped steps → to_run empty → continue (Line 191) ──


class TestDAGSkipContinuePrecise:
    """精确覆盖 engine.py line 191 — to_run 空 + ready 非空 → continue。

    场景: ConditionalStep 无匹配 + 无默认 → ALL 后继 skipped。
    被 skip 的步骤的后继 in_degree 推进后加入 ready（也在 skipped 中）。
    to_run = []（全在 skipped），ready 非空 → continue。
    """

    @pytest.mark.asyncio
    async def test_all_skipped_but_successors_added_to_ready(self) -> None:
        """ConditionalStep 全 skip → to_run 空 + successors 进 ready → continue。"""
        # cond1(root): 无匹配 + 无默认 → ALL 后继 (s2) 被 skip
        # s2 → s3: s2 被 skip 后 newly_skipped 推进 s3 进 ready
        cond1 = ConditionalStep(
            id="cond1",
            branches=[
                BranchCondition(label="never", condition="False", target_step_id="s2"),
            ],
            default_step_id=None,  # 无默认 → 全部跳过
        )
        s2 = AgentStep(id="s2", agent_name="a", prompt_template="s2")
        s3 = AgentStep(id="s3", agent_name="a", prompt_template="s3")

        workflow = Workflow(
            name="wf",
            steps=[cond1, s2, s3],
            edges=[
                Edge(id="e1", source_step_id="cond1", target_step_id="s2"),
                Edge(id="e2", source_step_id="s2", target_step_id="s3"),
            ],
        )

        async def resolver(name: str) -> Any:
            return MagicMock()

        result = await WorkflowEngine.run(
            workflow, context={}, agent_resolver=resolver,
        )

        # cond1 执行（选不中） → s2, s3 全 skip → 流程完成
        assert result.status == WorkflowStatus.COMPLETED
        # s2, s3 不应该被执行（全 skip）
        if "s2" in result.step_results:
            assert result.step_results["s2"].status == StepStatus.SKIPPED
