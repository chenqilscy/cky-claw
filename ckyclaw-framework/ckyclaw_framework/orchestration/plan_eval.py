"""PlanEvaluator — 规划-评估分离模块。

将 ExecutionPlan 的「生成」和「审查」分离为独立阶段，
实现三角审查模式：Planner 生成计划 → Evaluator 审查 → 质量门禁。

集成 S7 PlanGuard 的 5 项基础验证，并支持自定义评估标准。
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.orchestration.plan_guard import (
    ExecutionPlan,
    GuardCheckResult,
    PlanGuard,
    PlanGuardResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class EvaluationCriterion:
    """单项评估标准。

    Attributes:
        name: 标准名称。
        check: 检查函数（同步或异步），接受 ExecutionPlan 返回 bool。
        weight: 权重（用于加权评分）。
        message: 未通过时的提示信息。
    """

    name: str
    check: Callable[..., Any]
    weight: float = 1.0
    message: str = ""


@dataclass
class EvaluationResult:
    """评估结果。

    Attributes:
        approved: 是否通过评估。
        score: 加权评分（0.0-1.0）。
        checks: 各项检查结果（含 PlanGuard + 自定义标准）。
        suggestions: 改进建议列表。
    """

    approved: bool
    score: float
    checks: list[GuardCheckResult] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[GuardCheckResult]:
        """未通过的检查项。"""
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        """生成评估摘要。"""
        status = "✅ 通过" if self.approved else "❌ 未通过"
        lines = [f"评估结果: {status} (score={self.score:.2f})"]
        for c in self.checks:
            mark = "✓" if c.passed else "✗"
            lines.append(f"  {mark} {c.check_name}: {c.message}")
        if self.suggestions:
            lines.append("建议:")
            for s in self.suggestions:
                lines.append(f"  - {s}")
        return "\n".join(lines)


@dataclass
class PlanEvaluator:
    """ExecutionPlan 评估器。

    职责：对 ExecutionPlan 执行多维评估，包括：
    1. PlanGuard 基础验证（DAG 无环、能力匹配、Token 预算、Agent 可用性、超时合理性）
    2. 自定义评估标准（可扩展）

    三角审查模式：
    - PlannerAgent 产出 ExecutionPlan
    - PlanEvaluator 审查
    - 审查通过后才允许 Runner 执行

    Example:
        evaluator = PlanEvaluator(
            criteria=[
                EvaluationCriterion(
                    name="min_steps",
                    check=lambda plan: len(plan.steps) >= 2,
                    message="计划至少需要 2 个步骤",
                ),
            ],
            guard=PlanGuard(available_agents=["agent-a", "agent-b"]),
        )
        result = await evaluator.evaluate(plan)
        if result.approved:
            # 执行计划
            ...
    """

    criteria: list[EvaluationCriterion] = field(default_factory=list)
    """自定义评估标准列表。"""

    min_approval_score: float = 0.7
    """通过所需的最低加权评分。"""

    guard: PlanGuard | None = None
    """可选 PlanGuard 实例，用于基础验证。"""

    require_guard_pass: bool = True
    """是否要求 PlanGuard 全部通过才能批准。"""

    async def evaluate(self, plan: ExecutionPlan) -> EvaluationResult:
        """评估 ExecutionPlan。

        流程：
        1. 如有 PlanGuard，先执行 5 项基础验证
        2. 执行自定义评估标准
        3. 计算加权评分
        4. 根据 min_approval_score 和 guard 结果判断是否通过
        5. 生成改进建议

        Args:
            plan: 待评估的执行计划。

        Returns:
            评估结果。
        """
        all_checks: list[GuardCheckResult] = []
        suggestions: list[str] = []
        guard_passed = True

        # Step 1: PlanGuard 基础验证
        if self.guard is not None:
            guard_result: PlanGuardResult = self.guard.validate(plan)
            all_checks.extend(guard_result.checks)
            if not guard_result.approved:
                guard_passed = False
                for fc in guard_result.failed_checks:
                    suggestions.append(f"[PlanGuard] {fc.check_name}: {fc.message}")

        # Step 2: 自定义评估标准
        criteria_results = await self._run_criteria(plan)
        all_checks.extend(criteria_results)

        # Step 3: 加权评分（仅自定义标准参与评分）
        score = self._calc_score(criteria_results)

        # Step 4: 判断审批
        score_ok = score >= self.min_approval_score
        guard_ok = guard_passed or not self.require_guard_pass
        approved = score_ok and guard_ok

        # Step 5: 改进建议
        if not score_ok:
            suggestions.append(
                f"加权评分 {score:.2f} 低于阈值 {self.min_approval_score:.2f}"
            )
        for cr in criteria_results:
            if not cr.passed and cr.message:
                suggestions.append(cr.message)

        return EvaluationResult(
            approved=approved,
            score=score,
            checks=all_checks,
            suggestions=suggestions,
        )

    async def _run_criteria(
        self,
        plan: ExecutionPlan,
    ) -> list[GuardCheckResult]:
        """执行自定义评估标准（支持同步/异步）。"""
        results: list[GuardCheckResult] = []
        for criterion in self.criteria:
            try:
                check_result = criterion.check(plan)
                if inspect.isawaitable(check_result):
                    passed = await check_result
                else:
                    passed = check_result
            except Exception as exc:
                logger.warning(
                    "评估标准 '%s' 执行异常: %s",
                    criterion.name, exc,
                )
                passed = False

            results.append(GuardCheckResult(
                check_name=criterion.name,
                passed=bool(passed),
                message=criterion.message if not passed else "",
            ))
        return results

    def _calc_score(self, criteria_results: list[GuardCheckResult]) -> float:
        """计算自定义标准的加权评分。"""
        if not self.criteria:
            return 1.0  # 无自定义标准时默认满分

        total_weight = sum(c.weight for c in self.criteria)
        if total_weight == 0:
            return 1.0

        passed_weight = 0.0
        for criterion, result in zip(self.criteria, criteria_results, strict=False):
            if result.passed:
                passed_weight += criterion.weight

        return passed_weight / total_weight

    def add_criterion(self, criterion: EvaluationCriterion) -> None:
        """添加评估标准。"""
        self.criteria.append(criterion)
