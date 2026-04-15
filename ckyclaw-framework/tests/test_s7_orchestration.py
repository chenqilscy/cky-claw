"""S7 智能编排 — Framework 测试。

覆盖：
- PlanGuard 五项验证
- PlanStep / ExecutionPlan 数据类
- Mailbox InMemoryBackend
"""

from __future__ import annotations

import pytest

from ckyclaw_framework.orchestration import (
    ExecutionPlan,
    GuardCheckResult,
    PlanGuard,
    PlanGuardResult,
    PlanStep,
)

# ===========================================================================
# PlanStep & ExecutionPlan 数据类
# ===========================================================================


class TestPlanDataClasses:
    """PlanStep 和 ExecutionPlan 数据类。"""

    def test_plan_step_defaults(self) -> None:
        """PlanStep 默认值。"""
        step = PlanStep(step_id="s1", agent_name="agent-a", task="do something")
        assert step.depends_on == []
        assert step.required_capabilities == []
        assert step.estimated_tokens == 0
        assert step.timeout_seconds == 300.0

    def test_execution_plan_defaults(self) -> None:
        """ExecutionPlan 默认值。"""
        plan = ExecutionPlan(plan_id="p1")
        assert plan.steps == []
        assert plan.max_total_tokens == 100_000
        assert plan.max_timeout_seconds == 3600.0

    def test_guard_check_result(self) -> None:
        """GuardCheckResult 字段。"""
        result = GuardCheckResult(check_name="test", passed=True, message="ok")
        assert result.check_name == "test"
        assert result.passed

    def test_plan_guard_result_summary(self) -> None:
        """PlanGuardResult 摘要。"""
        r = PlanGuardResult(
            approved=False,
            checks=[
                GuardCheckResult(check_name="a", passed=True),
                GuardCheckResult(check_name="b", passed=False),
            ],
        )
        assert "1/2" in r.summary()
        assert len(r.failed_checks) == 1


# ===========================================================================
# PlanGuard 检查 1: DAG 无环
# ===========================================================================


class TestPlanGuardDAG:
    """DAG 无环检测。"""

    def test_no_dependencies(self) -> None:
        """无依赖计划通过。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task1"),
            PlanStep(step_id="s2", agent_name="a2", task="task2"),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        dag_check = result.checks[0]
        assert dag_check.passed

    def test_linear_dependencies(self) -> None:
        """线性依赖链通过。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task1"),
            PlanStep(step_id="s2", agent_name="a2", task="task2", depends_on=["s1"]),
            PlanStep(step_id="s3", agent_name="a3", task="task3", depends_on=["s2"]),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert result.checks[0].passed

    def test_cycle_detected(self) -> None:
        """循环依赖被检测。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task1", depends_on=["s2"]),
            PlanStep(step_id="s2", agent_name="a2", task="task2", depends_on=["s1"]),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        dag_check = result.checks[0]
        assert not dag_check.passed
        assert "循环" in dag_check.message

    def test_missing_dependency(self) -> None:
        """依赖不存在的步骤。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task1", depends_on=["nonexistent"]),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert not result.checks[0].passed
        assert "不存在" in result.checks[0].message

    def test_self_loop_detected(self) -> None:
        """自环检测。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task1", depends_on=["s1"]),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert not result.checks[0].passed


# ===========================================================================
# PlanGuard 检查 2: 能力匹配
# ===========================================================================


class TestPlanGuardCapability:
    """能力匹配检测。"""

    def test_no_capabilities_configured_passes(self) -> None:
        """未配置能力矩阵时跳过。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", required_capabilities=["coding"]),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        cap_check = result.checks[1]
        assert cap_check.passed

    def test_capabilities_matched(self) -> None:
        """能力匹配通过。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", required_capabilities=["coding"]),
        ])
        guard = PlanGuard(agent_capabilities={"a1": ["coding", "testing"]})
        result = guard.validate(plan)
        assert result.checks[1].passed

    def test_capabilities_mismatch(self) -> None:
        """能力不足。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", required_capabilities=["coding", "devops"]),
        ])
        guard = PlanGuard(agent_capabilities={"a1": ["coding"]})
        result = guard.validate(plan)
        assert not result.checks[1].passed


# ===========================================================================
# PlanGuard 检查 3: Token 预算
# ===========================================================================


class TestPlanGuardTokenBudget:
    """Token 预算检测。"""

    def test_within_budget(self) -> None:
        """在预算内。"""
        plan = ExecutionPlan(plan_id="p1", max_total_tokens=10000, steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", estimated_tokens=3000),
            PlanStep(step_id="s2", agent_name="a2", task="task", estimated_tokens=5000),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert result.checks[2].passed

    def test_over_budget(self) -> None:
        """超出预算。"""
        plan = ExecutionPlan(plan_id="p1", max_total_tokens=5000, steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", estimated_tokens=3000),
            PlanStep(step_id="s2", agent_name="a2", task="task", estimated_tokens=3000),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert not result.checks[2].passed
        assert "超过预算" in result.checks[2].message


# ===========================================================================
# PlanGuard 检查 4: Agent 可用性
# ===========================================================================


class TestPlanGuardAvailability:
    """Agent 可用性检测。"""

    def test_no_available_list_passes(self) -> None:
        """未配置可用列表时跳过。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="unknown", task="task"),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert result.checks[3].passed

    def test_all_available(self) -> None:
        """所有 Agent 可用。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task"),
        ])
        guard = PlanGuard(available_agents=["a1", "a2"])
        result = guard.validate(plan)
        assert result.checks[3].passed

    def test_unavailable_agent(self) -> None:
        """Agent 不可用。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a3", task="task"),
        ])
        guard = PlanGuard(available_agents=["a1", "a2"])
        result = guard.validate(plan)
        assert not result.checks[3].passed
        assert "a3" in result.checks[3].message


# ===========================================================================
# PlanGuard 检查 5: 超时合理性
# ===========================================================================


class TestPlanGuardTimeout:
    """超时合理性检测。"""

    def test_reasonable_timeout(self) -> None:
        """合理超时。"""
        plan = ExecutionPlan(plan_id="p1", max_timeout_seconds=600, steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", timeout_seconds=100),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert result.checks[4].passed

    def test_negative_timeout(self) -> None:
        """负超时。"""
        plan = ExecutionPlan(plan_id="p1", steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", timeout_seconds=-1),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert not result.checks[4].passed

    def test_step_exceeds_max(self) -> None:
        """单步超过总限制。"""
        plan = ExecutionPlan(plan_id="p1", max_timeout_seconds=60, steps=[
            PlanStep(step_id="s1", agent_name="a1", task="task", timeout_seconds=120),
        ])
        guard = PlanGuard()
        result = guard.validate(plan)
        assert not result.checks[4].passed


# ===========================================================================
# PlanGuard 综合验证
# ===========================================================================


class TestPlanGuardIntegration:
    """PlanGuard 综合测试。"""

    def test_all_checks_pass(self) -> None:
        """全部通过。"""
        plan = ExecutionPlan(
            plan_id="p1",
            max_total_tokens=50000,
            max_timeout_seconds=600,
            steps=[
                PlanStep(step_id="s1", agent_name="a1", task="task1",
                         estimated_tokens=10000, timeout_seconds=100,
                         required_capabilities=["coding"]),
                PlanStep(step_id="s2", agent_name="a2", task="task2",
                         depends_on=["s1"], estimated_tokens=15000, timeout_seconds=200,
                         required_capabilities=["testing"]),
            ],
        )
        guard = PlanGuard(
            available_agents=["a1", "a2"],
            agent_capabilities={"a1": ["coding"], "a2": ["testing"]},
        )
        result = guard.validate(plan)
        assert result.approved
        assert len(result.checks) == 5
        assert all(c.passed for c in result.checks)

    def test_multiple_failures(self) -> None:
        """多项失败。"""
        plan = ExecutionPlan(
            plan_id="p1",
            max_total_tokens=100,
            steps=[
                PlanStep(step_id="s1", agent_name="a1", task="task",
                         estimated_tokens=200, timeout_seconds=-1,
                         required_capabilities=["magic"]),
            ],
        )
        guard = PlanGuard(
            available_agents=["a2"],
            agent_capabilities={"a1": ["coding"]},
        )
        result = guard.validate(plan)
        assert not result.approved
        assert len(result.failed_checks) >= 3

    def test_empty_plan_passes(self) -> None:
        """空计划通过所有检查。"""
        plan = ExecutionPlan(plan_id="p1")
        guard = PlanGuard()
        result = guard.validate(plan)
        assert result.approved


# ===========================================================================
# Mailbox InMemoryBackend
# ===========================================================================


class TestInMemoryMailboxBackend:
    """InMemoryMailboxBackend 测试。"""

    @pytest.mark.anyio()
    async def test_send_and_receive(self) -> None:
        """发送并接收消息。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend, MailboxMessage

        backend = InMemoryMailboxBackend()
        msg = MailboxMessage(
            run_id="run-1",
            from_agent="agent-a",
            to_agent="agent-b",
            content="hello",
        )
        await backend.send(msg)

        received = await backend.receive("agent-b", run_id="run-1")
        assert len(received) == 1
        assert received[0].content == "hello"

    @pytest.mark.anyio()
    async def test_receive_unread_only(self) -> None:
        """仅接收未读消息。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend, MailboxMessage

        backend = InMemoryMailboxBackend()
        msg = MailboxMessage(run_id="r1", from_agent="a", to_agent="b", content="hi")
        await backend.send(msg)
        await backend.mark_read(msg.message_id)

        received = await backend.receive("b", unread_only=True)
        assert len(received) == 0

        all_msgs = await backend.receive("b", unread_only=False)
        assert len(all_msgs) == 1

    @pytest.mark.anyio()
    async def test_conversation(self) -> None:
        """获取双向对话历史。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend, MailboxMessage

        backend = InMemoryMailboxBackend()
        await backend.send(MailboxMessage(run_id="r1", from_agent="a", to_agent="b", content="hi"))
        await backend.send(MailboxMessage(run_id="r1", from_agent="b", to_agent="a", content="hello"))
        await backend.send(MailboxMessage(run_id="r1", from_agent="a", to_agent="c", content="unrelated"))

        conv = await backend.get_conversation("r1", "a", "b")
        assert len(conv) == 2

    @pytest.mark.anyio()
    async def test_delete_run_messages(self) -> None:
        """删除 Run 消息。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend, MailboxMessage

        backend = InMemoryMailboxBackend()
        await backend.send(MailboxMessage(run_id="r1", from_agent="a", to_agent="b", content="msg1"))
        await backend.send(MailboxMessage(run_id="r2", from_agent="a", to_agent="b", content="msg2"))

        await backend.delete_run_messages("r1")

        r1_msgs = await backend.receive("b", run_id="r1", unread_only=False)
        r2_msgs = await backend.receive("b", run_id="r2", unread_only=False)
        assert len(r1_msgs) == 0
        assert len(r2_msgs) == 1

    @pytest.mark.anyio()
    async def test_receive_wrong_agent(self) -> None:
        """接收方不匹配时收不到消息。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend, MailboxMessage

        backend = InMemoryMailboxBackend()
        await backend.send(MailboxMessage(run_id="r1", from_agent="a", to_agent="b", content="hi"))

        received = await backend.receive("c")
        assert len(received) == 0

    @pytest.mark.anyio()
    async def test_mark_read_nonexistent(self) -> None:
        """标记不存在的消息已读（静默跳过）。"""
        from ckyclaw_framework.mailbox import InMemoryMailboxBackend

        backend = InMemoryMailboxBackend()
        await backend.mark_read("nonexistent")  # 不应抛出


# ===========================================================================
# Exports
# ===========================================================================


class TestOrchestrationExports:
    """公共 API 导出。"""

    def test_orchestration_exports(self) -> None:
        """orchestration 包导出。"""
        from ckyclaw_framework.orchestration import (
            PlanGuard,
            PlanStep,
        )
        assert PlanGuard is not None
        assert PlanStep is not None

    def test_mailbox_exports(self) -> None:
        """mailbox 包导出。"""
        from ckyclaw_framework.mailbox import (
            InMemoryMailboxBackend,
            MailboxBackend,
            MailboxMessage,
        )
        assert MailboxBackend is not None
        assert InMemoryMailboxBackend is not None
        assert MailboxMessage is not None
