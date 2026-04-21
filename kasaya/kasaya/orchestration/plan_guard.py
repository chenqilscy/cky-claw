"""PlanGuard — 执行计划验证器。

对 Agent 编排计划执行五项检查：
1. DAG 无环检测（依赖关系无循环）
2. 能力匹配（Agent 标签与任务需求匹配）
3. Token 预估（总 Token 不超过预算）
4. 成员可用性检查
5. 超时合理性校验
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """计划步骤。"""

    step_id: str
    """步骤唯一标识。"""

    agent_name: str
    """负责执行的 Agent 名称。"""

    task: str
    """任务描述。"""

    depends_on: list[str] = field(default_factory=list)
    """依赖的前置步骤 ID 列表。"""

    required_capabilities: list[str] = field(default_factory=list)
    """完成此步骤所需的能力标签。"""

    estimated_tokens: int = 0
    """预估 Token 消耗。"""

    timeout_seconds: float = 300.0
    """超时限制（秒）。"""


@dataclass
class ExecutionPlan:
    """Agent 编排执行计划。"""

    plan_id: str
    """计划唯一标识。"""

    steps: list[PlanStep] = field(default_factory=list)
    """有序步骤列表。"""

    max_total_tokens: int = 100_000
    """总 Token 预算上限。"""

    max_timeout_seconds: float = 3600.0
    """总超时上限（秒）。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """扩展元数据。"""


@dataclass
class GuardCheckResult:
    """单项检查结果。"""

    check_name: str
    """检查名称。"""

    passed: bool
    """是否通过。"""

    message: str = ""
    """描述信息。"""

    details: dict[str, Any] = field(default_factory=dict)
    """详细数据。"""


@dataclass
class PlanGuardResult:
    """PlanGuard 综合验证结果。"""

    approved: bool
    """是否全部通过。"""

    checks: list[GuardCheckResult] = field(default_factory=list)
    """各项检查结果。"""

    @property
    def failed_checks(self) -> list[GuardCheckResult]:
        """返回未通过的检查项。"""
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        """生成摘要描述。"""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.passed)
        return f"PlanGuard: {passed}/{total} checks passed"


class PlanGuard:
    """执行计划五项检查验证器。"""

    def __init__(
        self,
        *,
        available_agents: list[str] | None = None,
        agent_capabilities: dict[str, list[str]] | None = None,
    ) -> None:
        """初始化 PlanGuard。

        Args:
            available_agents: 可用的 Agent 名称列表。
            agent_capabilities: Agent 名称 → 能力标签映射。
        """
        self._available_agents = set(available_agents or [])
        self._capabilities = agent_capabilities or {}

    def validate(self, plan: ExecutionPlan) -> PlanGuardResult:
        """执行全部验证检查。

        Args:
            plan: 要验证的执行计划。

        Returns:
            PlanGuardResult 包含各项检查结果。
        """
        checks = [
            self._check_dag_acyclic(plan),
            self._check_capability_match(plan),
            self._check_token_budget(plan),
            self._check_agent_availability(plan),
            self._check_timeout_reasonable(plan),
        ]
        approved = all(c.passed for c in checks)

        result = PlanGuardResult(approved=approved, checks=checks)
        if not approved:
            logger.warning("PlanGuard 验证失败: %s", result.summary())
        return result

    def _check_dag_acyclic(self, plan: ExecutionPlan) -> GuardCheckResult:
        """检查 1: DAG 无环检测。

        使用拓扑排序（Kahn's）检测步骤依赖是否存在循环。
        """
        step_ids = {s.step_id for s in plan.steps}
        # 构建邻接表和入度
        in_degree: dict[str, int] = {s.step_id: 0 for s in plan.steps}
        adj: dict[str, list[str]] = {s.step_id: [] for s in plan.steps}

        for step in plan.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    return GuardCheckResult(
                        check_name="dag_acyclic",
                        passed=False,
                        message=f"步骤 '{step.step_id}' 依赖了不存在的步骤 '{dep}'",
                        details={"missing_dep": dep, "step": step.step_id},
                    )
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited < len(step_ids):
            cycle_nodes = [sid for sid, deg in in_degree.items() if deg > 0]
            return GuardCheckResult(
                check_name="dag_acyclic",
                passed=False,
                message=f"依赖图存在循环, 涉及步骤: {cycle_nodes}",
                details={"cycle_nodes": cycle_nodes},
            )

        return GuardCheckResult(
            check_name="dag_acyclic",
            passed=True,
            message="依赖图无循环",
        )

    def _check_capability_match(self, plan: ExecutionPlan) -> GuardCheckResult:
        """检查 2: 能力匹配。

        验证每个步骤的 required_capabilities 是否被对应 Agent 覆盖。
        """
        if not self._capabilities:
            return GuardCheckResult(
                check_name="capability_match",
                passed=True,
                message="未配置能力矩阵, 跳过检查",
            )

        mismatches: list[dict[str, Any]] = []
        for step in plan.steps:
            if not step.required_capabilities:
                continue
            agent_caps = set(self._capabilities.get(step.agent_name, []))
            missing = [c for c in step.required_capabilities if c not in agent_caps]
            if missing:
                mismatches.append({
                    "step": step.step_id,
                    "agent": step.agent_name,
                    "missing": missing,
                })

        if mismatches:
            return GuardCheckResult(
                check_name="capability_match",
                passed=False,
                message=f"{len(mismatches)} 个步骤的能力需求未满足",
                details={"mismatches": mismatches},
            )

        return GuardCheckResult(
            check_name="capability_match",
            passed=True,
            message="所有步骤的能力需求已满足",
        )

    def _check_token_budget(self, plan: ExecutionPlan) -> GuardCheckResult:
        """检查 3: Token 预算。

        验证所有步骤的预估 Token 总和不超过预算。
        """
        total_estimated = sum(s.estimated_tokens for s in plan.steps)

        if total_estimated > plan.max_total_tokens:
            return GuardCheckResult(
                check_name="token_budget",
                passed=False,
                message=f"预估 Token 总量 {total_estimated} 超过预算 {plan.max_total_tokens}",
                details={"estimated": total_estimated, "budget": plan.max_total_tokens},
            )

        return GuardCheckResult(
            check_name="token_budget",
            passed=True,
            message=f"预估 Token 总量 {total_estimated} 在预算内",
            details={"estimated": total_estimated, "budget": plan.max_total_tokens},
        )

    def _check_agent_availability(self, plan: ExecutionPlan) -> GuardCheckResult:
        """检查 4: 成员可用性。

        验证计划中引用的 Agent 都在可用列表中。
        """
        if not self._available_agents:
            return GuardCheckResult(
                check_name="agent_availability",
                passed=True,
                message="未配置可用 Agent 列表, 跳过检查",
            )

        unavailable = []
        for step in plan.steps:
            if step.agent_name not in self._available_agents:
                unavailable.append(step.agent_name)

        if unavailable:
            return GuardCheckResult(
                check_name="agent_availability",
                passed=False,
                message=f"以下 Agent 不可用: {list(set(unavailable))}",
                details={"unavailable": list(set(unavailable))},
            )

        return GuardCheckResult(
            check_name="agent_availability",
            passed=True,
            message="所有 Agent 可用",
        )

    def _check_timeout_reasonable(self, plan: ExecutionPlan) -> GuardCheckResult:
        """检查 5: 超时合理性。

        验证单步超时和总超时在合理范围内。
        """
        issues: list[str] = []

        for step in plan.steps:
            if step.timeout_seconds <= 0:
                issues.append(f"步骤 '{step.step_id}' 超时 <= 0")
            elif step.timeout_seconds > plan.max_timeout_seconds:
                issues.append(
                    f"步骤 '{step.step_id}' 超时 {step.timeout_seconds}s 超过总限制 {plan.max_timeout_seconds}s"
                )

        total_serial_time = sum(s.timeout_seconds for s in plan.steps)
        if total_serial_time > plan.max_timeout_seconds * 3:
            issues.append(f"步骤串行总超时 {total_serial_time}s 超过总限制的 3 倍")

        if issues:
            return GuardCheckResult(
                check_name="timeout_reasonable",
                passed=False,
                message=f"超时配置异常: {'; '.join(issues)}",
                details={"issues": issues},
            )

        return GuardCheckResult(
            check_name="timeout_reasonable",
            passed=True,
            message="超时配置合理",
        )
