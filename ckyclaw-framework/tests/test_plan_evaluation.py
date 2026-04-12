"""E3 PlanEvaluator 测试 — 规划-评估分离。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.orchestration.plan_eval import (
    EvaluationCriterion,
    EvaluationResult,
    PlanEvaluator,
)
from ckyclaw_framework.orchestration.plan_guard import (
    ExecutionPlan,
    GuardCheckResult,
    PlanGuard,
    PlanStep,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_plan(n_steps: int = 3) -> ExecutionPlan:
    """创建简单的测试 ExecutionPlan。"""
    steps = [
        PlanStep(
            step_id=f"s{i}",
            agent_name=f"agent-{i}",
            task=f"任务 {i}",
            depends_on=[f"s{i - 1}"] if i > 0 else [],
            estimated_tokens=1000,
            timeout_seconds=60.0,
        )
        for i in range(n_steps)
    ]
    return ExecutionPlan(plan_id="test-plan", steps=steps)


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    """EvaluationResult 测试。"""

    def test_failed_checks(self) -> None:
        """failed_checks 过滤。"""
        checks = [
            GuardCheckResult(check_name="a", passed=True),
            GuardCheckResult(check_name="b", passed=False, message="失败"),
        ]
        r = EvaluationResult(approved=False, score=0.5, checks=checks)
        assert len(r.failed_checks) == 1
        assert r.failed_checks[0].check_name == "b"

    def test_summary_approved(self) -> None:
        """通过时的摘要。"""
        r = EvaluationResult(approved=True, score=1.0)
        s = r.summary()
        assert "通过" in s
        assert "1.00" in s

    def test_summary_rejected(self) -> None:
        """未通过时的摘要。"""
        r = EvaluationResult(
            approved=False,
            score=0.3,
            suggestions=["需要更多步骤"],
        )
        s = r.summary()
        assert "未通过" in s
        assert "需要更多步骤" in s


# ---------------------------------------------------------------------------
# EvaluationCriterion
# ---------------------------------------------------------------------------


class TestEvaluationCriterion:
    """EvaluationCriterion 测试。"""

    def test_defaults(self) -> None:
        """默认值。"""
        c = EvaluationCriterion(name="test", check=lambda p: True)
        assert c.weight == 1.0
        assert c.message == ""

    def test_custom_weight(self) -> None:
        """自定义权重。"""
        c = EvaluationCriterion(name="test", check=lambda p: True, weight=2.0)
        assert c.weight == 2.0


# ---------------------------------------------------------------------------
# PlanEvaluator — 基础评估（无 PlanGuard）
# ---------------------------------------------------------------------------


class TestPlanEvaluatorBasic:
    """不使用 PlanGuard 的基础评估。"""

    @pytest.mark.asyncio
    async def test_no_criteria_approved(self) -> None:
        """无自定义标准时默认通过（满分）。"""
        ev = PlanEvaluator()
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_all_pass(self) -> None:
        """所有标准通过。"""
        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(
                name="has_steps",
                check=lambda p: len(p.steps) > 0,
            ),
            EvaluationCriterion(
                name="reasonable_tokens",
                check=lambda p: sum(s.estimated_tokens for s in p.steps) < 50000,
            ),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True
        assert result.score == pytest.approx(1.0)
        assert len(result.checks) == 2

    @pytest.mark.asyncio
    async def test_partial_pass(self) -> None:
        """部分标准通过 — 分数反映通过比例。"""
        ev = PlanEvaluator(
            criteria=[
                EvaluationCriterion(
                    name="pass",
                    check=lambda p: True,
                    weight=1.0,
                ),
                EvaluationCriterion(
                    name="fail",
                    check=lambda p: False,
                    weight=1.0,
                    message="这项未通过",
                ),
            ],
            min_approval_score=0.8,
        )
        result = await ev.evaluate(_simple_plan())
        assert result.approved is False
        assert result.score == pytest.approx(0.5)
        assert "这项未通过" in result.suggestions

    @pytest.mark.asyncio
    async def test_all_fail(self) -> None:
        """全部未通过。"""
        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(name="f1", check=lambda p: False, message="失败1"),
            EvaluationCriterion(name="f2", check=lambda p: False, message="失败2"),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.approved is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_weighted_score(self) -> None:
        """加权评分计算。"""
        ev = PlanEvaluator(
            criteria=[
                EvaluationCriterion(name="heavy", check=lambda p: True, weight=3.0),
                EvaluationCriterion(name="light", check=lambda p: False, weight=1.0),
            ],
            min_approval_score=0.5,
        )
        result = await ev.evaluate(_simple_plan())
        # 3/(3+1) = 0.75 >= 0.5
        assert result.approved is True
        assert result.score == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# PlanEvaluator — 异步标准
# ---------------------------------------------------------------------------


class TestAsyncCriteria:
    """异步评估标准测试。"""

    @pytest.mark.asyncio
    async def test_async_check(self) -> None:
        """支持异步 check 函数。"""
        async def async_check(plan: ExecutionPlan) -> bool:
            return len(plan.steps) >= 2

        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(name="async_test", check=async_check),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_mixed_sync_async(self) -> None:
        """同步和异步标准混合。"""
        async def async_check(plan: ExecutionPlan) -> bool:
            return True

        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(name="sync", check=lambda p: True),
            EvaluationCriterion(name="async", check=async_check),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True
        assert result.score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_check_exception_treated_as_fail(self) -> None:
        """check 函数抛异常时视为未通过。"""
        def bad_check(plan: ExecutionPlan) -> bool:
            raise RuntimeError("boom")

        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(name="bad", check=bad_check, message="出错了"),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.approved is False
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# PlanEvaluator — 集成 PlanGuard
# ---------------------------------------------------------------------------


class TestWithPlanGuard:
    """集成 PlanGuard 测试。"""

    @pytest.mark.asyncio
    async def test_guard_pass(self) -> None:
        """PlanGuard 通过 + 无自定义标准 → 批准。"""
        plan = _simple_plan()
        agents = [s.agent_name for s in plan.steps]
        guard = PlanGuard(available_agents=agents)
        ev = PlanEvaluator(guard=guard)
        result = await ev.evaluate(plan)
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_guard_fail_blocks_approval(self) -> None:
        """PlanGuard 未通过时阻止批准（require_guard_pass=True）。"""
        # 构造循环依赖 → DAG 检查失败
        plan = ExecutionPlan(
            plan_id="cyclic",
            steps=[
                PlanStep(step_id="a", agent_name="x", task="t1", depends_on=["b"]),
                PlanStep(step_id="b", agent_name="y", task="t2", depends_on=["a"]),
            ],
        )
        guard = PlanGuard(available_agents=["x", "y"])
        ev = PlanEvaluator(guard=guard)
        result = await ev.evaluate(plan)
        assert result.approved is False
        assert any("[PlanGuard]" in s for s in result.suggestions)

    @pytest.mark.asyncio
    async def test_guard_fail_ignored_when_not_required(self) -> None:
        """require_guard_pass=False 时 PlanGuard 失败不阻止批准。"""
        # 循环依赖 → guard 失败
        plan = ExecutionPlan(
            plan_id="cyclic",
            steps=[
                PlanStep(step_id="a", agent_name="x", task="t1", depends_on=["b"]),
                PlanStep(step_id="b", agent_name="y", task="t2", depends_on=["a"]),
            ],
        )
        guard = PlanGuard(available_agents=["x", "y"])
        ev = PlanEvaluator(guard=guard, require_guard_pass=False)
        result = await ev.evaluate(plan)
        # 无自定义标准 → score=1.0 → 通过
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_guard_plus_criteria(self) -> None:
        """PlanGuard + 自定义标准联合评估。"""
        plan = _simple_plan()
        agents = [s.agent_name for s in plan.steps]
        guard = PlanGuard(available_agents=agents)
        ev = PlanEvaluator(
            guard=guard,
            criteria=[
                EvaluationCriterion(
                    name="has_steps",
                    check=lambda p: len(p.steps) >= 2,
                ),
            ],
        )
        result = await ev.evaluate(plan)
        assert result.approved is True
        # checks 应包含 guard + criteria
        assert len(result.checks) > 1

    @pytest.mark.asyncio
    async def test_guard_checks_in_result(self) -> None:
        """PlanGuard 检查结果包含在 result.checks 中。"""
        plan = _simple_plan()
        agents = [s.agent_name for s in plan.steps]
        guard = PlanGuard(available_agents=agents)
        ev = PlanEvaluator(guard=guard)
        result = await ev.evaluate(plan)
        guard_check_names = [c.check_name for c in result.checks]
        # PlanGuard 的 5 项检查
        assert "dag_acyclic" in guard_check_names


# ---------------------------------------------------------------------------
# PlanEvaluator — add_criterion
# ---------------------------------------------------------------------------


class TestAddCriterion:
    """动态添加标准测试。"""

    @pytest.mark.asyncio
    async def test_add_criterion(self) -> None:
        """添加标准后生效。"""
        ev = PlanEvaluator()
        ev.add_criterion(
            EvaluationCriterion(
                name="min_2_steps",
                check=lambda p: len(p.steps) >= 2,
            ),
        )
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True
        assert len(result.checks) == 1


# ---------------------------------------------------------------------------
# 边界条件
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界条件测试。"""

    @pytest.mark.asyncio
    async def test_empty_plan(self) -> None:
        """空计划评估。"""
        plan = ExecutionPlan(plan_id="empty")
        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(
                name="has_steps",
                check=lambda p: len(p.steps) > 0,
                message="计划不能为空",
            ),
        ])
        result = await ev.evaluate(plan)
        assert result.approved is False
        assert "计划不能为空" in result.suggestions

    @pytest.mark.asyncio
    async def test_zero_weight_criteria(self) -> None:
        """权重全为 0 时默认满分。"""
        ev = PlanEvaluator(criteria=[
            EvaluationCriterion(name="z", check=lambda p: False, weight=0.0),
        ])
        result = await ev.evaluate(_simple_plan())
        assert result.score == 1.0
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_min_approval_score_zero(self) -> None:
        """min_approval_score=0 时总是通过（除非 guard 阻止）。"""
        ev = PlanEvaluator(
            criteria=[EvaluationCriterion(name="f", check=lambda p: False)],
            min_approval_score=0.0,
        )
        result = await ev.evaluate(_simple_plan())
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_single_step_plan(self) -> None:
        """单步骤计划。"""
        plan = ExecutionPlan(
            plan_id="single",
            steps=[PlanStep(step_id="s0", agent_name="a0", task="唯一任务")],
        )
        guard = PlanGuard(available_agents=["a0"])
        ev = PlanEvaluator(guard=guard)
        result = await ev.evaluate(plan)
        assert result.approved is True
