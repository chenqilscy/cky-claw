"""WorkflowEngine — DAG 驱动的工作流执行引擎。

执行模型：
1. Kahn 拓扑排序计算 in_degree
2. Ready Queue：in_degree=0 的步骤入队
3. 主循环：取出 ready 步骤 → 过滤已跳过 → 执行 → 更新后继 in_degree → 新 ready 入队
4. ParallelStep 通过 asyncio.TaskGroup 真正并行执行
5. LoopStep 使用 while 语义（先判断条件再执行 body）
6. ConditionalStep 求值分支条件，选择目标步骤，其余后继标记跳过
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace
from ckyclaw_framework.workflow.config import WorkflowRunConfig
from ckyclaw_framework.workflow.evaluator import evaluate
from ckyclaw_framework.workflow.result import StepResult, WorkflowResult, WorkflowStatus
from ckyclaw_framework.workflow.step import (
    AgentStep,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    Step,
    StepStatus,
)
from ckyclaw_framework.workflow.validator import validate_workflow_strict

if TYPE_CHECKING:
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.runner.result import RunResult
    from ckyclaw_framework.tracing.processor import TraceProcessor
    from ckyclaw_framework.workflow.workflow import Workflow

# 模板渲染正则：匹配 {{key}} 占位符
_TEMPLATE_RE = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")


class AgentNotFoundError(Exception):
    """agent_resolver 找不到指定 Agent 时抛出。"""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"Agent not found: '{agent_name}'")


# Type alias: agent_resolver(agent_name) -> Agent
AgentResolver = Callable[[str], Coroutine[Any, Any, "Agent"]]


class WorkflowEngine:
    """DAG 驱动的工作流执行引擎。"""

    @staticmethod
    async def run(
        workflow: Workflow,
        context: dict[str, Any] | None = None,
        *,
        agent_resolver: AgentResolver,
        config: WorkflowRunConfig | None = None,
        cancel_event: asyncio.Event | None = None,
        trace_processors: list[TraceProcessor] | None = None,
    ) -> WorkflowResult:
        """执行工作流，返回 WorkflowResult。

        Args:
            workflow: 工作流定义
            context: 初始上下文字典（会被步骤输出更新）
            agent_resolver: 异步函数，通过 agent_name 解析 Agent 实例
            config: 工作流运行配置
            cancel_event: 取消信号
            trace_processors: 追踪处理器列表
        """
        config = config or WorkflowRunConfig()
        ctx = dict(context) if context else {}
        cancel = cancel_event or asyncio.Event()
        processors = trace_processors or []

        # 初始化结果
        now = datetime.now(UTC)
        result = WorkflowResult(
            workflow_name=workflow.name,
            status=WorkflowStatus.RUNNING,
            context=ctx,
            started_at=now,
        )

        # Tracing
        trace: Trace | None = None
        if config.tracing_enabled:
            trace = Trace(workflow_name=workflow.name)
            for p in processors:
                await p.on_trace_start(trace)

        try:
            # 严格验证 DAG
            validate_workflow_strict(workflow)

            await _execute_dag(
                workflow=workflow,
                ctx=ctx,
                result=result,
                agent_resolver=agent_resolver,
                config=config,
                cancel=cancel,
                trace=trace,
                processors=processors,
            )
        except asyncio.CancelledError:
            result.status = WorkflowStatus.CANCELLED
            result.error = "工作流被取消"
        except Exception as exc:
            result.status = WorkflowStatus.FAILED
            result.error = str(exc)
        finally:
            result.finished_at = datetime.now(UTC)
            if result.started_at:
                delta = result.finished_at - result.started_at
                result.duration_ms = int(delta.total_seconds() * 1000)
            result.context = ctx
            result.trace = trace
            if trace and config.tracing_enabled:
                trace.end_time = datetime.now(UTC)
                for p in processors:
                    await p.on_trace_end(trace)

        return result


async def _execute_dag(
    workflow: Workflow,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
) -> None:
    """Ready-queue 驱动的 DAG 执行。"""
    step_map: dict[str, Step] = {s.id: s for s in workflow.steps}
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {s.id: 0 for s in workflow.steps}

    for edge in workflow.edges:
        adj[edge.source_step_id].append(edge.target_step_id)
        in_degree[edge.target_step_id] += 1

    # 初始 ready queue
    ready: list[str] = [sid for sid, deg in in_degree.items() if deg == 0]
    skipped: set[str] = set()
    processed_skipped: set[str] = set()

    # 超时保护
    timeout = config.workflow_timeout or workflow.timeout
    deadline = (asyncio.get_event_loop().time() + timeout) if timeout else None

    while ready:
        if cancel.is_set():
            raise asyncio.CancelledError()

        if deadline is not None and asyncio.get_event_loop().time() > deadline:
            raise TimeoutError("工作流执行超时")

        # 过滤掉已跳过的步骤
        to_run = [sid for sid in ready if sid not in skipped]
        ready.clear()

        # 推进被跳过步骤的后继（仅处理新增的跳过步骤）
        newly_skipped = skipped - processed_skipped
        for sid in newly_skipped:
            for succ in adj[sid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    ready.append(succ)
        processed_skipped.update(newly_skipped)

        if not to_run and not ready:
            break

        if not to_run:
            continue

        # 多个 ready 步骤并行执行（TaskGroup）
        if len(to_run) == 1:
            sid = to_run[0]
            step = step_map[sid]
            await _execute_step(
                step=step,
                ctx=ctx,
                result=result,
                agent_resolver=agent_resolver,
                config=config,
                cancel=cancel,
                trace=trace,
                processors=processors,
                skipped=skipped,
                adj=adj,
                step_map=step_map,
            )
        else:
            async with asyncio.TaskGroup() as tg:
                for sid in to_run:
                    step = step_map[sid]
                    tg.create_task(
                        _execute_step(
                            step=step,
                            ctx=ctx,
                            result=result,
                            agent_resolver=agent_resolver,
                            config=config,
                            cancel=cancel,
                            trace=trace,
                            processors=processors,
                            skipped=skipped,
                            adj=adj,
                            step_map=step_map,
                        )
                    )

        # 更新后继 in_degree
        for sid in to_run:
            for succ in adj[sid]:
                if succ not in skipped:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0 and succ not in ready:
                        ready.append(succ)

    # 判断最终状态
    if result.status == WorkflowStatus.RUNNING:
        has_failed = any(sr.status == StepStatus.FAILED for sr in result.step_results.values())
        result.status = WorkflowStatus.FAILED if has_failed else WorkflowStatus.COMPLETED


async def _execute_step(
    step: Step,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
    skipped: set[str],
    adj: dict[str, list[str]],
    step_map: dict[str, Step],
) -> None:
    """执行单个步骤（含重试）。"""
    started_at = datetime.now(UTC)

    # 创建 Span
    span = _create_span(step, trace)
    if span:
        for p in processors:
            await p.on_span_start(span)

    retry = step.retry_config
    max_attempts = (retry.max_retries + 1) if retry else 1
    delay = retry.delay_seconds if retry else 0.0
    backoff = retry.backoff_multiplier if retry else 1.0
    last_error: str | None = None

    for attempt in range(max_attempts):
        if cancel.is_set():
            _record_step_result(result, step.id, StepStatus.CANCELLED, started_at, error="已取消")
            await _end_span(span, SpanStatus.CANCELLED, processors)
            return

        try:
            timeout = step.timeout or config.tool_timeout
            if timeout:
                await asyncio.wait_for(
                    _dispatch_step(
                        step=step,
                        ctx=ctx,
                        result=result,
                        agent_resolver=agent_resolver,
                        config=config,
                        cancel=cancel,
                        trace=trace,
                        processors=processors,
                        skipped=skipped,
                        adj=adj,
                        step_map=step_map,
                    ),
                    timeout=timeout,
                )
            else:
                await _dispatch_step(
                    step=step,
                    ctx=ctx,
                    result=result,
                    agent_resolver=agent_resolver,
                    config=config,
                    cancel=cancel,
                    trace=trace,
                    processors=processors,
                    skipped=skipped,
                    adj=adj,
                    step_map=step_map,
                )

            # 成功：记录结果
            output = _collect_output(step, ctx)
            _record_step_result(result, step.id, StepStatus.COMPLETED, started_at, output=output)
            await _end_span(span, SpanStatus.COMPLETED, processors, output=output)
            return

        except AgentNotFoundError:
            # Agent 找不到，不重试
            last_error = f"Agent not found: '{step.agent_name}'" if isinstance(step, AgentStep) else "Agent not found"
            break

        except TimeoutError as exc:
            last_error = f"步骤超时: {exc}"
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay *= backoff
            continue

        except Exception as exc:
            last_error = str(exc)
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay *= backoff
            continue

    # 所有重试均失败
    _record_step_result(result, step.id, StepStatus.FAILED, started_at, error=last_error)
    await _end_span(span, SpanStatus.FAILED, processors, error=last_error)

    if config.fail_fast:
        raise RuntimeError(f"步骤 '{step.id}' 执行失败: {last_error}")


async def _dispatch_step(
    step: Step,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
    skipped: set[str],
    adj: dict[str, list[str]],
    step_map: dict[str, Step],
) -> None:
    """根据步骤类型分派执行。"""
    if isinstance(step, AgentStep):
        await _run_agent_step(step, ctx, agent_resolver, config)
    elif isinstance(step, ParallelStep):
        await _run_parallel_step(step, ctx, result, agent_resolver, config, cancel, trace, processors)
    elif isinstance(step, ConditionalStep):
        _run_conditional_step(step, ctx, skipped, adj, step_map)
    elif isinstance(step, LoopStep):
        await _run_loop_step(step, ctx, result, agent_resolver, config, cancel, trace, processors)
    else:
        raise ValueError(f"未知步骤类型: {step.type}")


# ── AgentStep ──────────────────────────────────────────────────────────

async def _run_agent_step(
    step: AgentStep,
    ctx: dict[str, Any],
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
) -> None:
    """执行 Agent 步骤。"""
    agent = await agent_resolver(step.agent_name)
    if agent is None:
        raise AgentNotFoundError(step.agent_name)

    # 构建输入
    step_input = _build_step_input(step, ctx)

    # 渲染 prompt
    prompt = _render_template(step.prompt_template, step_input) if step.prompt_template else ""
    if not prompt:
        # 无模板时，将输入序列化为字符串
        prompt = str(step_input) if step_input else ""

    # 构建 RunConfig（禁用 tracing 避免重复）
    run_config = RunConfig(
        model_provider=config.model_provider,
        tracing_enabled=False,
    )

    run_result: RunResult = await Runner.run(
        agent=agent,
        input=prompt,
        config=run_config,
        max_turns=step.max_turns,
    )

    # 写入 context
    _write_output(step, ctx, run_result.output)


# ── ParallelStep ───────────────────────────────────────────────────────

async def _run_parallel_step(
    step: ParallelStep,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
) -> None:
    """并行执行所有 sub_steps（asyncio.TaskGroup 真正并行）。"""
    errors: list[str] = []

    if step.fail_policy == "fail_fast":
        # fail_fast: 任何一个失败立即取消全部
        try:
            async with asyncio.TaskGroup() as tg:
                for sub in step.sub_steps:
                    tg.create_task(_run_sub_step(sub, ctx, result, agent_resolver, config, cancel, trace, processors))
        except* Exception as eg:
            for exc in eg.exceptions:
                errors.append(str(exc))
    else:
        # all_settled: 等待全部完成，收集所有错误
        tasks = [
            asyncio.create_task(_run_sub_step(sub, ctx, result, agent_resolver, config, cancel, trace, processors))
            for sub in step.sub_steps
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                errors.append(str(r))

    if errors:
        raise RuntimeError(f"ParallelStep '{step.id}' 子步骤失败: {'; '.join(errors)}")


async def _run_sub_step(
    sub: AgentStep | ConditionalStep,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
) -> None:
    """执行 ParallelStep / LoopStep 的子步骤。"""
    started_at = datetime.now(UTC)
    span = _create_span(sub, trace)
    if span:
        for p in processors:
            await p.on_span_start(span)

    try:
        if isinstance(sub, AgentStep):
            await _run_agent_step(sub, ctx, agent_resolver, config)
        elif isinstance(sub, ConditionalStep):
            # 子步骤中的 Conditional 不影响 DAG 跳过
            _eval_conditional_inline(sub, ctx)
        else:
            raise ValueError(f"不支持的子步骤类型: {type(sub).__name__}")

        output = _collect_output(sub, ctx)
        _record_step_result(result, sub.id, StepStatus.COMPLETED, started_at, output=output)
        await _end_span(span, SpanStatus.COMPLETED, processors, output=output)
    except Exception as exc:
        _record_step_result(result, sub.id, StepStatus.FAILED, started_at, error=str(exc))
        await _end_span(span, SpanStatus.FAILED, processors, error=str(exc))
        raise


# ── ConditionalStep ────────────────────────────────────────────────────

def _run_conditional_step(
    step: ConditionalStep,
    ctx: dict[str, Any],
    skipped: set[str],
    adj: dict[str, list[str]],
    step_map: dict[str, Step],
) -> None:
    """求值条件分支，选择目标步骤，其余后继标记为跳过。"""
    chosen_id: str | None = None

    for branch in step.branches:
        if evaluate(branch.condition, ctx):
            chosen_id = branch.target_step_id
            break

    if chosen_id is None:
        chosen_id = step.default_step_id

    # 获取所有后继步骤
    successors = set(adj.get(step.id, []))

    # 将非选中的后继全部标记为跳过
    if chosen_id:
        for sid in successors:
            if sid != chosen_id:
                _mark_subtree_skipped(sid, adj, skipped)
    else:
        # 无匹配 + 无默认 → 跳过所有后继
        for sid in successors:
            _mark_subtree_skipped(sid, adj, skipped)


def _eval_conditional_inline(step: ConditionalStep, ctx: dict[str, Any]) -> None:
    """内联条件求值（在 Parallel/Loop 子步骤中使用，不影响 DAG 跳过）。"""
    for branch in step.branches:
        if evaluate(branch.condition, ctx):
            ctx[f"_branch_{step.id}"] = branch.label
            return
    if step.default_step_id:
        ctx[f"_branch_{step.id}"] = "default"


def _mark_subtree_skipped(
    step_id: str,
    adj: dict[str, list[str]],
    skipped: set[str],
) -> None:
    """递归标记步骤及其所有可达后继为跳过。"""
    if step_id in skipped:
        return
    skipped.add(step_id)
    for succ in adj.get(step_id, []):
        _mark_subtree_skipped(succ, adj, skipped)


# ── LoopStep ───────────────────────────────────────────────────────────

async def _run_loop_step(
    step: LoopStep,
    ctx: dict[str, Any],
    result: WorkflowResult,
    agent_resolver: AgentResolver,
    config: WorkflowRunConfig,
    cancel: asyncio.Event,
    trace: Trace | None,
    processors: list[TraceProcessor],
) -> None:
    """while 语义循环：先判断条件再执行 body_steps。"""
    iterations: list[dict[str, Any]] = []
    iteration = 0

    while iteration < step.max_iterations:
        if cancel.is_set():
            raise asyncio.CancelledError()

        # while 语义：先检查条件（空 condition 视为 True → 靠 max_iterations 控制）
        if step.condition and not evaluate(step.condition, ctx):
            break

        # 顺序执行 body_steps
        for body_step in step.body_steps:
            if cancel.is_set():
                raise asyncio.CancelledError()

            await _run_sub_step(body_step, ctx, result, agent_resolver, config, cancel, trace, processors)

        # 收集本轮迭代输出
        if step.iteration_output_key:
            iteration_snapshot = {k: ctx.get(k) for k in _get_body_output_keys(step)}
            iterations.append(iteration_snapshot)

        iteration += 1

    # 写入迭代结果
    if step.iteration_output_key:
        ctx[step.iteration_output_key] = iterations


# ── 辅助函数 ───────────────────────────────────────────────────────────

def _build_step_input(step: Step, ctx: dict[str, Any]) -> dict[str, Any]:
    """根据 step.io.input_keys 从 context 提取输入。"""
    if not step.io.input_keys:
        return dict(ctx)
    return {local_key: ctx.get(ctx_key) for local_key, ctx_key in step.io.input_keys.items()}


def _write_output(step: Step, ctx: dict[str, Any], output: Any) -> None:
    """将步骤输出写入 context。"""
    if step.io.output_keys:
        if isinstance(output, dict):
            for local_key, ctx_key in step.io.output_keys.items():
                ctx[ctx_key] = output.get(local_key, output)
        else:
            # 非字典输出 → 所有 output_keys 映射同一个值
            for _, ctx_key in step.io.output_keys.items():
                ctx[ctx_key] = output
    else:
        # 无显式映射 → 以 step.id 为 key
        ctx[step.id] = output


def _collect_output(step: Step, ctx: dict[str, Any]) -> dict[str, Any]:
    """收集步骤的 context 输出。"""
    if step.io.output_keys:
        return {ctx_key: ctx.get(ctx_key) for _, ctx_key in step.io.output_keys.items()}
    key = step.id
    return {key: ctx.get(key)} if key in ctx else {}


def _render_template(template: str, context: dict[str, Any]) -> str:
    """渲染 {{key}} 占位符。支持 dot-separated path。"""
    def _replace(match: re.Match[str]) -> str:
        path = match.group(1)
        value: Any = context
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return match.group(0)  # 无法解析，保留原样
        return str(value) if value is not None else ""

    return _TEMPLATE_RE.sub(_replace, template)


def _get_body_output_keys(step: LoopStep) -> list[str]:
    """收集 LoopStep body_steps 的所有 output context keys。"""
    keys: list[str] = []
    for body in step.body_steps:
        if body.io.output_keys:
            keys.extend(body.io.output_keys.values())
        else:
            keys.append(body.id)
    return keys


def _record_step_result(
    result: WorkflowResult,
    step_id: str,
    status: StepStatus,
    started_at: datetime,
    output: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """记录步骤执行结果。"""
    finished_at = datetime.now(UTC)
    delta = finished_at - started_at
    result.step_results[step_id] = StepResult(
        step_id=step_id,
        status=status,
        output=output or {},
        error=error,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int(delta.total_seconds() * 1000),
    )


def _create_span(step: Step, trace: Trace | None) -> Span | None:
    """为步骤创建 Span（无 trace 时返回 None）。"""
    if trace is None:
        return None
    span = Span(
        trace_id=trace.trace_id,
        type=SpanType.WORKFLOW_STEP,
        name=f"{step.type.value}:{step.id}",
        status=SpanStatus.RUNNING,
        metadata={"step_type": step.type.value},
    )
    trace.spans.append(span)
    return span


async def _end_span(
    span: Span | None,
    status: SpanStatus,
    processors: list[TraceProcessor],
    output: Any = None,
    error: str | None = None,
) -> None:
    """结束 Span。"""
    if span is None:
        return
    span.end_time = datetime.now(UTC)
    span.status = status
    if output is not None:
        span.output = output
    if error:
        span.metadata["error"] = error
    for p in processors:
        await p.on_span_end(span)
