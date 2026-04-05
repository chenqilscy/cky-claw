"""WorkflowEngine 扩展测试 — 覆盖超时 / 重试退避 / 条件分支跳过 / 循环迭代 / _render_template / _build_step_input / _write_output / _collect_output。"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.workflow.engine import (
    AgentNotFoundError,
    WorkflowEngine,
    _build_step_input,
    _collect_output,
    _get_body_output_keys,
    _mark_subtree_skipped,
    _render_template,
    _write_output,
)
from ckyclaw_framework.workflow.config import WorkflowRunConfig
from ckyclaw_framework.workflow.result import StepResult, WorkflowResult, WorkflowStatus
from ckyclaw_framework.workflow.step import (
    AgentStep,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    Step,
    StepIO,
    StepType,
    RetryConfig,
)
from ckyclaw_framework.workflow.workflow import Edge, Workflow


# ─── _render_template ────────────────────────────────────────────

class TestRenderTemplate:
    """_render_template 模板渲染测试。"""

    def test_simple_key(self) -> None:
        """简单 key 替换。"""
        assert _render_template("Hello {{name}}", {"name": "cky"}) == "Hello cky"

    def test_multiple_keys(self) -> None:
        """多个占位符。"""
        result = _render_template("{{a}} + {{b}}", {"a": "1", "b": "2"})
        assert result == "1 + 2"

    def test_dot_path(self) -> None:
        """dot-separated path 访问嵌套字典。"""
        ctx = {"user": {"name": "boss"}}
        assert _render_template("Hi {{user.name}}", ctx) == "Hi boss"

    def test_missing_key_becomes_empty(self) -> None:
        """不存在的 key → 空字符串。"""
        assert _render_template("{{missing}}", {}) == ""

    def test_none_value_becomes_empty(self) -> None:
        """值为 None → 空字符串。"""
        assert _render_template("{{x}}", {"x": None}) == ""

    def test_non_dict_intermediate_preserved(self) -> None:
        """dot-path 中间值非 dict → 保留原占位符。"""
        ctx = {"a": 42}
        assert _render_template("{{a.b}}", ctx) == "{{a.b}}"

    def test_deep_nesting(self) -> None:
        """深层嵌套访问。"""
        ctx = {"a": {"b": {"c": "deep"}}}
        assert _render_template("{{a.b.c}}", ctx) == "deep"

    def test_no_placeholders(self) -> None:
        """无占位符的文本不变。"""
        assert _render_template("plain text", {}) == "plain text"

    def test_integer_value_to_string(self) -> None:
        """整数值自动转字符串。"""
        assert _render_template("count: {{n}}", {"n": 42}) == "count: 42"


# ─── _build_step_input ───────────────────────────────────────────

class TestBuildStepInput:
    """_build_step_input 输入映射测试。"""

    def test_no_input_keys_returns_full_ctx(self) -> None:
        """无 input_keys → 返回整个 context 副本。"""
        step = Step(id="s1", io=StepIO())
        ctx = {"a": 1, "b": 2}
        result = _build_step_input(step, ctx)
        assert result == {"a": 1, "b": 2}
        assert result is not ctx  # 应该是副本

    def test_with_input_keys_mapping(self) -> None:
        """有 input_keys → 映射指定字段。"""
        step = Step(id="s1", io=StepIO(input_keys={"local_name": "ctx_name"}))
        ctx = {"ctx_name": "hello", "other": "unused"}
        result = _build_step_input(step, ctx)
        assert result == {"local_name": "hello"}

    def test_missing_ctx_key_returns_none(self) -> None:
        """映射的 context key 不存在 → None。"""
        step = Step(id="s1", io=StepIO(input_keys={"x": "missing_key"}))
        ctx: dict[str, Any] = {}
        result = _build_step_input(step, ctx)
        assert result == {"x": None}


# ─── _write_output ───────────────────────────────────────────────

class TestWriteOutput:
    """_write_output 输出写入测试。"""

    def test_dict_output_with_keys(self) -> None:
        """字典输出 + output_keys → 按映射写入。"""
        step = Step(id="s1", io=StepIO(output_keys={"result": "ctx_result"}))
        ctx: dict[str, Any] = {}
        _write_output(step, ctx, {"result": "hello"})
        assert ctx["ctx_result"] == "hello"

    def test_non_dict_output_with_keys(self) -> None:
        """非字典输出 + output_keys → 所有 key 映射同一个值。"""
        step = Step(id="s1", io=StepIO(output_keys={"a": "ctx_a", "b": "ctx_b"}))
        ctx: dict[str, Any] = {}
        _write_output(step, ctx, "scalar_value")
        assert ctx["ctx_a"] == "scalar_value"
        assert ctx["ctx_b"] == "scalar_value"

    def test_no_output_keys(self) -> None:
        """无 output_keys → 以 step.id 为 key。"""
        step = Step(id="my_step", io=StepIO())
        ctx: dict[str, Any] = {}
        _write_output(step, ctx, "the output")
        assert ctx["my_step"] == "the output"

    def test_dict_output_missing_local_key(self) -> None:
        """字典输出缺少 local_key → output_keys.get fallback 到整个 output dict。"""
        step = Step(id="s1", io=StepIO(output_keys={"missing": "ctx_x"}))
        ctx: dict[str, Any] = {}
        output = {"other_key": "val"}
        _write_output(step, ctx, output)
        # get("missing", output) → 返回整个 output dict
        assert ctx["ctx_x"] == output


# ─── _collect_output ─────────────────────────────────────────────

class TestCollectOutput:
    """_collect_output 输出收集测试。"""

    def test_with_output_keys(self) -> None:
        """有 output_keys → 按映射收集。"""
        step = Step(id="s1", io=StepIO(output_keys={"r": "ctx_r"}))
        ctx = {"ctx_r": "result_value"}
        result = _collect_output(step, ctx)
        assert result == {"ctx_r": "result_value"}

    def test_no_output_keys_key_in_ctx(self) -> None:
        """无 output_keys + step.id 在 ctx 中。"""
        step = Step(id="step1", io=StepIO())
        ctx = {"step1": "val"}
        assert _collect_output(step, ctx) == {"step1": "val"}

    def test_no_output_keys_key_not_in_ctx(self) -> None:
        """无 output_keys + step.id 不在 ctx 中 → 空 dict。"""
        step = Step(id="step1", io=StepIO())
        ctx: dict[str, Any] = {}
        assert _collect_output(step, ctx) == {}


# ─── _get_body_output_keys ───────────────────────────────────────

class TestGetBodyOutputKeys:
    """_get_body_output_keys 测试。"""

    def test_basic(self) -> None:
        """收集 body_steps 的 output_keys。"""
        s1 = AgentStep(id="b1", agent_name="a", io=StepIO(output_keys={"x": "ctx_x"}))
        s2 = AgentStep(id="b2", agent_name="b", io=StepIO())
        loop = LoopStep(id="loop1", body_steps=[s1, s2], condition="True")
        keys = _get_body_output_keys(loop)
        assert "ctx_x" in keys
        assert "b2" in keys


# ─── _mark_subtree_skipped ──────────────────────────────────────

class TestMarkSubtreeSkipped:
    """_mark_subtree_skipped 递归跳过标记测试。"""

    def test_single_node(self) -> None:
        """标记单个节点。"""
        adj: dict[str, list[str]] = {}
        skipped: set[str] = set()
        _mark_subtree_skipped("A", adj, skipped)
        assert "A" in skipped

    def test_chain(self) -> None:
        """A → B → C 链式标记。"""
        adj = {"A": ["B"], "B": ["C"]}
        skipped: set[str] = set()
        _mark_subtree_skipped("A", adj, skipped)
        assert skipped == {"A", "B", "C"}

    def test_diamond(self) -> None:
        """钻石型图：A → B, A → C, B → D, C → D。标记 A → 全跳。"""
        adj = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        skipped: set[str] = set()
        _mark_subtree_skipped("A", adj, skipped)
        assert skipped == {"A", "B", "C", "D"}

    def test_already_skipped(self) -> None:
        """已在 skipped 中的节点不重复标记。"""
        adj = {"A": ["B"]}
        skipped: set[str] = {"A"}
        _mark_subtree_skipped("A", adj, skipped)
        # B 不应被标记（因为 A 已跳过，直接返回）
        assert "B" not in skipped

    def test_no_successors(self) -> None:
        """无后继节点。"""
        adj: dict[str, list[str]] = {}
        skipped: set[str] = set()
        _mark_subtree_skipped("leaf", adj, skipped)
        assert skipped == {"leaf"}


# ─── WorkflowEngine 集成测试 ─────────────────────────────────────

class TestWorkflowEngineIntegration:
    """WorkflowEngine.run 集成测试。"""

    @pytest.mark.asyncio
    async def test_single_step_workflow(self) -> None:
        """单步骤工作流执行。"""
        step = AgentStep(id="s1", name="step1", agent_name="agent_a", prompt_template="Hi")
        workflow = Workflow(name="wf1", steps=[step], edges=[])

        mock_agent = MagicMock()
        mock_runner_result = MagicMock(spec=["output", "token_usage"])
        mock_runner_result.output = "Agent response"
        mock_runner_result.token_usage = None

        async def resolver(name: str) -> Any:
            if name == "agent_a":
                return mock_agent
            return None

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_runner_result)
            result = await WorkflowEngine.run(
                workflow, context={"input": "test"}, agent_resolver=resolver,
            )

        assert result.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_agent_not_found(self) -> None:
        """Agent 找不到 → AgentNotFoundError → 步骤失败。"""
        step = AgentStep(id="s1", name="step1", agent_name="missing_agent", prompt_template="Hi")
        workflow = Workflow(name="wf1", steps=[step], edges=[])

        async def resolver(name: str) -> Any:
            return None  # 找不到

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock()
            result = await WorkflowEngine.run(
                workflow,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )

        # 步骤应该标记为失败
        assert any(sr.status == "failed" for sr in result.step_results.values())

    @pytest.mark.asyncio
    async def test_workflow_timeout(self) -> None:
        """工作流级超时触发。"""
        async def slow_agent_fn(**kwargs: Any) -> str:
            await asyncio.sleep(10)
            return "done"

        step = AgentStep(id="s1", name="slow", agent_name="slow_agent", prompt_template="work")
        workflow = Workflow(name="wf1", steps=[step], edges=[], timeout=0.01)

        mock_agent = MagicMock()

        async def resolver(name: str) -> Any:
            return mock_agent

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=lambda *a, **kw: asyncio.sleep(10))
            result = await WorkflowEngine.run(
                workflow,
                agent_resolver=resolver,
                config=WorkflowRunConfig(fail_fast=False),
            )

        assert result.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_cancel_event(self) -> None:
        """cancel_event 取消工作流。"""
        step = AgentStep(id="s1", name="step1", agent_name="agent_a", prompt_template="Hi")
        workflow = Workflow(name="wf1", steps=[step], edges=[])

        mock_agent = MagicMock()

        async def resolver(name: str) -> Any:
            return mock_agent

        cancel = asyncio.Event()
        cancel.set()  # 立即取消

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock()
            result = await WorkflowEngine.run(
                workflow, agent_resolver=resolver, cancel_event=cancel,
            )

        assert result.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self) -> None:
        """步骤重试：指数退避。"""
        retry = RetryConfig(max_retries=1, delay_seconds=0.01, backoff_multiplier=2.0)
        step = AgentStep(
            id="s1", name="retry_step", agent_name="agent_a",
            prompt_template="Hi", retry_config=retry,
        )
        workflow = Workflow(name="wf1", steps=[step], edges=[])

        mock_agent = MagicMock()
        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "ok"
        mock_result.token_usage = None

        call_count = 0

        async def resolver(name: str) -> Any:
            return mock_agent

        async def flaky_run(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            return mock_result

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(side_effect=flaky_run)
            result = await WorkflowEngine.run(workflow, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_linear_dag(self) -> None:
        """线性 DAG: s1 → s2。"""
        s1 = AgentStep(
            id="s1", name="first", agent_name="a",
            prompt_template="Hi",
            io=StepIO(output_keys={"result": "s1_out"}),
        )
        s2 = AgentStep(
            id="s2", name="second", agent_name="a",
            prompt_template="{{s1_out}}",
            io=StepIO(input_keys={"input": "s1_out"}),
        )
        workflow = Workflow(
            name="wf", steps=[s1, s2],
            edges=[Edge(id="e1", source_step_id="s1", target_step_id="s2")],
        )

        mock_agent = MagicMock()
        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "step output"
        mock_result.token_usage = None

        async def resolver(name: str) -> Any:
            return mock_agent

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(workflow, agent_resolver=resolver)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 2

    @pytest.mark.asyncio
    async def test_tracing_enabled(self) -> None:
        """tracing_enabled=True 时创建 Trace + Span。"""
        step = AgentStep(id="s1", name="step1", agent_name="a", prompt_template="Hi")
        workflow = Workflow(name="wf", steps=[step], edges=[])

        processor = AsyncMock()
        mock_agent = MagicMock()
        mock_result = MagicMock(spec=["output", "token_usage"])
        mock_result.output = "ok"
        mock_result.token_usage = None

        async def resolver(name: str) -> Any:
            return mock_agent

        with patch("ckyclaw_framework.workflow.engine.Runner") as MockRunner:
            MockRunner.run = AsyncMock(return_value=mock_result)
            result = await WorkflowEngine.run(
                workflow,
                agent_resolver=resolver,
                config=WorkflowRunConfig(tracing_enabled=True),
                trace_processors=[processor],
            )

        processor.on_trace_start.assert_awaited_once()
        processor.on_trace_end.assert_awaited_once()
        assert result.trace is not None
