"""Runner — Agent 执行引擎，驱动 Agent Loop 完成推理和工具调用。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError, classify_tool_risk
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError, OutputGuardrailTripwireError
from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
from ckyclaw_framework.handoff.handoff import Handoff
from ckyclaw_framework.model._converter import (
    messages_to_litellm,
    model_response_to_assistant_message,
    tool_result_to_message,
)
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelProvider, ModelResponse, ToolCall
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.runner.hooks import _invoke_hook
from ckyclaw_framework.runner.result import RunResult, StreamEvent, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimStrategy, HistoryTrimmer
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace

logger = logging.getLogger(__name__)

# Handoff 工具名前缀约定
_HANDOFF_TOOL_PREFIX = "transfer_to_"


def _build_response_format(output_type: type | None) -> dict[str, Any] | None:
    """为结构化输出构建 response_format 参数。

    当 Agent.output_type 是 Pydantic BaseModel 子类时，构建 JSON Schema response_format
    交给 LLM（OpenAI、智谱等支持 response_format 的模型）。
    """
    if output_type is None:
        return None
    # Pydantic BaseModel: 使用 model_json_schema() 生成 JSON Schema
    if hasattr(output_type, "model_json_schema"):
        schema = output_type.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": output_type.__name__,
                "schema": schema,
                "strict": False,
            },
        }
    # 普通 dict 型 JSON Schema（从 API/DB 传入的原始 schema）
    if isinstance(output_type, dict):
        return {"type": "json_object"}
    return None


def _parse_structured_output(raw: str, output_type: type | None) -> Any:
    """将 LLM 返回的文本解析为结构化输出。

    Args:
        raw: LLM 返回的原始文本。
        output_type: Agent.output_type。

    Returns:
        解析后的结构化对象，或原始字符串（解析失败时 fallback）。
    """
    if output_type is None or not raw:
        return raw
    # Pydantic BaseModel
    if hasattr(output_type, "model_validate_json"):
        try:
            return output_type.model_validate_json(raw)
        except Exception:
            # Fallback: 尝试从文本中提取 JSON 块
            try:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                return output_type.model_validate_json(raw[start:end])
            except Exception:
                logger.warning("Failed to parse structured output for %s, returning raw text", output_type.__name__)
                return raw
    return raw


def _build_trim_config(config: RunConfig) -> HistoryTrimConfig | None:
    """从 RunConfig 构建 HistoryTrimConfig。任何 trim 字段非空即启用裁剪。"""
    if config.max_history_tokens is None and config.max_history_messages is None:
        return None
    return HistoryTrimConfig(
        strategy=config.history_trim_strategy or HistoryTrimStrategy.TOKEN_BUDGET,
        max_history_tokens=config.max_history_tokens or 8000,
        max_history_messages=config.max_history_messages or 100,
    )


async def _build_system_message(agent: Agent, run_context: RunContext) -> Message:
    """构建 system 消息，注入 Agent instructions。

    支持三种 instructions 类型：
    - str: 静态文本
    - Callable[[RunContext], str]: 同步动态指令
    - Callable[[RunContext], Awaitable[str]]: 异步动态指令
    """
    if callable(agent.instructions):
        result = agent.instructions(run_context)
        # 检测 async callable 返回的 Awaitable
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            text = await result
        else:
            text = result  # type: ignore[assignment]
    else:
        text = agent.instructions or ""
    # output_type: 注入 JSON Schema 描述到 system prompt 作为 fallback 指引
    if agent.output_type is not None and hasattr(agent.output_type, "model_json_schema"):
        schema = agent.output_type.model_json_schema()
        hint = (
            f"\n\nYou MUST respond with a valid JSON object conforming to the following JSON Schema:\n"
            f"```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```\n"
            f"Do NOT include any text outside the JSON object."
        )
        text = text + hint
    return Message(role=MessageRole.SYSTEM, content=text)


def _build_tool_schemas(agent: Agent, run_ctx: RunContext | None = None) -> list[dict[str, Any]]:
    """从 Agent 的 tools + handoffs 构建 OpenAI tool schemas。

    condition 字段不为 None 时，仅在 condition(run_ctx) 返回 True 时包含该工具。
    """
    schemas: list[dict[str, Any]] = []
    for tool in agent.tools:
        if tool.condition is not None and run_ctx is not None:
            if not tool.condition(run_ctx):
                continue
        schemas.append(tool.to_openai_schema())
    # Handoff 生成特殊工具
    for target in agent.handoffs:
        if isinstance(target, Handoff):
            tool_name = target.resolved_tool_name
            description = target.resolved_tool_description
            # Handoff input_type: 将 Pydantic schema 转换为工具参数
            if target.input_type is not None and hasattr(target.input_type, "model_json_schema"):
                parameters = target.input_type.model_json_schema()
                # 确保 parameters 有 type: object
                parameters.setdefault("type", "object")
            else:
                parameters = {"type": "object", "properties": {}}
        else:
            tool_name = f"{_HANDOFF_TOOL_PREFIX}{target.name}"
            description = f"Transfer conversation to {target.name}: {target.description}"
            parameters = {"type": "object", "properties": {}}
        schemas.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": parameters,
            },
        })
    return schemas


def _resolve_model(agent: Agent, config: RunConfig | None) -> str:
    """确定使用的模型（RunConfig 覆盖 > Agent 定义 > 默认值）。"""
    if config and config.model:
        return config.model
    if agent.model:
        return agent.model
    return "gpt-4o-mini"


def _resolve_settings(agent: Agent, config: RunConfig | None) -> ModelSettings | None:
    """确定模型参数。"""
    if config and config.model_settings:
        return config.model_settings
    return agent.model_settings


def _resolve_provider(config: RunConfig | None) -> ModelProvider:
    """获取 ModelProvider 实例。"""
    if config and config.model_provider:
        return config.model_provider
    return LiteLLMProvider()


def _accumulate_usage(total: TokenUsage, delta: TokenUsage | None) -> None:
    """累加 token 消耗。"""
    if delta:
        total.prompt_tokens += delta.prompt_tokens
        total.completion_tokens += delta.completion_tokens
        total.total_tokens += delta.total_tokens


def _normalize_input(input_data: str | list[Message]) -> list[Message]:
    """将用户输入标准化为 Message 列表。"""
    if isinstance(input_data, str):
        return [Message(role=MessageRole.USER, content=input_data)]
    return list(input_data)


def _find_tool(agent: Agent, name: str) -> FunctionTool | None:
    """在 Agent.tools 中按名称查找工具。"""
    for tool in agent.tools:
        if tool.name == name:
            return tool
    return None


def _find_handoff_target(agent: Agent, tool_name: str) -> tuple[Agent, Handoff | None] | None:
    """检查 tool_name 是否是 handoff 请求。返回 (目标 Agent, Handoff 配置) 或 None。"""
    for target in agent.handoffs:
        if isinstance(target, Handoff):
            if target.resolved_tool_name == tool_name:
                return (target.agent, target)
        else:
            expected_name = f"{_HANDOFF_TOOL_PREFIX}{target.name}"
            if expected_name == tool_name:
                return (target, None)
    return None


async def _execute_input_guardrails(
    guardrails: list[InputGuardrail],
    run_context: RunContext,
    input_text: str,
    tracing: _TracingCtx | None = None,
    *,
    parallel: bool = False,
) -> None:
    """执行 Input Guardrails。

    parallel=False（默认）: 串行短路，首个 Tripwire 触发后立即中断。
    parallel=True: 并行执行所有 Guardrail，收集全部结果后报告首个触发项。
    """
    if parallel and len(guardrails) > 1:
        await _execute_input_guardrails_parallel(guardrails, run_context, input_text, tracing)
        return

    for guardrail in guardrails:
        # 条件启用：检查 condition
        if guardrail.condition is not None:
            try:
                if not guardrail.condition(run_context):
                    logger.debug("Input guardrail '%s' skipped by condition", guardrail.name)
                    continue
            except Exception:
                logger.warning("Input guardrail '%s' condition raised exception, treating as enabled", guardrail.name)

        # Tracing: Guardrail Span
        guardrail_span = None
        if tracing and tracing.active:
            guardrail_span = Span(
                trace_id=tracing.trace.trace_id if tracing.trace else "",
                parent_span_id=tracing._agent_span.span_id if tracing._agent_span else None,
                type=SpanType.GUARDRAIL,
                name=guardrail.name,
                status=SpanStatus.RUNNING,
            )
            if tracing.trace:
                tracing.trace.spans.append(guardrail_span)
            for p in tracing.processors:
                await p.on_span_start(guardrail_span)

        try:
            result: GuardrailResult = await guardrail.guardrail_function(run_context, input_text)
        except Exception as e:
            logger.exception("Input guardrail '%s' raised an exception", guardrail.name)
            if guardrail_span and tracing:
                await tracing.end_span(
                    guardrail_span,
                    output=str(e),
                    status=SpanStatus.FAILED,
                )
            raise InputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=f"Guardrail execution error: {e}",
            ) from e

        metadata = {
            "guardrail_name": guardrail.name,
            "guardrail_type": "input",
            "triggered": result.tripwire_triggered,
            "message": result.message,
        }
        if guardrail_span and tracing:
            guardrail_span.metadata = metadata
            status = SpanStatus.COMPLETED if not result.tripwire_triggered else SpanStatus.FAILED
            await tracing.end_span(guardrail_span, output=result.message, status=status)

        if result.tripwire_triggered:
            raise InputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=result.message,
            )


async def _execute_input_guardrails_parallel(
    guardrails: list[InputGuardrail],
    run_context: RunContext,
    input_text: str,
    tracing: _TracingCtx | None = None,
) -> None:
    """并行执行 Input Guardrails，收集所有结果后报告首个触发项。"""
    # 条件过滤（异常时当作启用）
    active: list[InputGuardrail] = []
    for g in guardrails:
        if g.condition is None:
            active.append(g)
        else:
            try:
                if g.condition(run_context):
                    active.append(g)
            except Exception:
                logger.warning("Input guardrail '%s' condition raised exception, treating as enabled", g.name)
                active.append(g)
    if not active:
        return

    results: list[tuple[InputGuardrail, GuardrailResult | Exception]] = []

    async def _run_one(g: InputGuardrail) -> tuple[InputGuardrail, GuardrailResult | Exception]:
        try:
            r = await g.guardrail_function(run_context, input_text)
            return (g, r)
        except Exception as e:
            return (g, e)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_run_one(g)) for g in active]

    results = [t.result() for t in tasks]

    # 报告结果
    for guardrail, result in results:
        if isinstance(result, Exception):
            raise InputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=f"Guardrail execution error: {result}",
            )
        if result.tripwire_triggered:
            raise InputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=result.message,
            )


async def _execute_output_guardrails(
    guardrails: list[OutputGuardrail],
    run_context: RunContext,
    output_text: str,
    tracing: _TracingCtx | None = None,
    *,
    parallel: bool = False,
) -> None:
    """执行 Output Guardrails。

    parallel=False（默认）: 串行短路，首个 Tripwire 触发后立即中断。
    parallel=True: 并行执行所有 Guardrail，收集全部结果后报告首个触发项。
    """
    if parallel and len(guardrails) > 1:
        await _execute_output_guardrails_parallel(guardrails, run_context, output_text, tracing)
        return

    for guardrail in guardrails:
        # 条件启用：检查 condition
        if guardrail.condition is not None:
            try:
                if not guardrail.condition(run_context):
                    logger.debug("Output guardrail '%s' skipped by condition", guardrail.name)
                    continue
            except Exception:
                logger.warning("Output guardrail '%s' condition raised exception, treating as enabled", guardrail.name)

        # Tracing: Guardrail Span
        guardrail_span = None
        if tracing and tracing.active:
            guardrail_span = Span(
                trace_id=tracing.trace.trace_id if tracing.trace else "",
                parent_span_id=tracing._agent_span.span_id if tracing._agent_span else None,
                type=SpanType.GUARDRAIL,
                name=guardrail.name,
                status=SpanStatus.RUNNING,
            )
            if tracing.trace:
                tracing.trace.spans.append(guardrail_span)
            for p in tracing.processors:
                await p.on_span_start(guardrail_span)

        try:
            result: GuardrailResult = await guardrail.guardrail_function(run_context, output_text)
        except Exception as e:
            logger.exception("Output guardrail '%s' raised an exception", guardrail.name)
            if guardrail_span and tracing:
                await tracing.end_span(
                    guardrail_span,
                    output=str(e),
                    status=SpanStatus.FAILED,
                )
            raise OutputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=f"Guardrail execution error: {e}",
            ) from e

        metadata = {
            "guardrail_name": guardrail.name,
            "guardrail_type": "output",
            "triggered": result.tripwire_triggered,
            "message": result.message,
        }
        if guardrail_span and tracing:
            guardrail_span.metadata = metadata
            status = SpanStatus.COMPLETED if not result.tripwire_triggered else SpanStatus.FAILED
            await tracing.end_span(guardrail_span, output=result.message, status=status)

        if result.tripwire_triggered:
            raise OutputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=result.message,
            )


async def _execute_output_guardrails_parallel(
    guardrails: list[OutputGuardrail],
    run_context: RunContext,
    output_text: str,
    tracing: _TracingCtx | None = None,
) -> None:
    """并行执行 Output Guardrails，收集所有结果后报告首个触发项。"""
    # 条件过滤（异常时当作启用）
    active: list[OutputGuardrail] = []
    for g in guardrails:
        if g.condition is None:
            active.append(g)
        else:
            try:
                if g.condition(run_context):
                    active.append(g)
            except Exception:
                logger.warning("Output guardrail '%s' condition raised exception, treating as enabled", g.name)
                active.append(g)
    if not active:
        return

    async def _run_one(g: OutputGuardrail) -> tuple[OutputGuardrail, GuardrailResult | Exception]:
        try:
            r = await g.guardrail_function(run_context, output_text)
            return (g, r)
        except Exception as e:
            return (g, e)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_run_one(g)) for g in active]

    results = [t.result() for t in tasks]

    for guardrail, result in results:
        if isinstance(result, Exception):
            raise OutputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=f"Guardrail execution error: {result}",
            )
        if result.tripwire_triggered:
            raise OutputGuardrailTripwireError(
                guardrail_name=guardrail.name,
                message=result.message,
            )


def _resolve_approval_mode(agent: Agent, config: RunConfig | None) -> ApprovalMode:
    """确定审批模式（RunConfig 覆盖 > Agent 定义 > 默认 full-auto）。"""
    if config and config.approval_mode is not None:
        return config.approval_mode
    if agent.approval_mode is not None:
        return agent.approval_mode
    return ApprovalMode.FULL_AUTO


async def _check_approval(
    run_context: RunContext,
    handler: ApprovalHandler | None,
    mode: ApprovalMode,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    tool_approval_required: bool = False,
) -> None:
    """检查工具调用是否需要审批。需要时调用 handler 并处理结果。

    full-auto: 直接返回（不审批）。
    suggest: 所有工具调用需审批。
    auto-edit: 安全操作自动执行，高风险需审批（基于 classify_tool_risk）。
    """
    if mode == ApprovalMode.FULL_AUTO:
        return
    if mode == ApprovalMode.AUTO_EDIT:
        # auto-edit: 使用风险分级判断是否需要审批
        needs_approval = classify_tool_risk(tool_name, approval_required=tool_approval_required)
        if not needs_approval:
            return
        # 高风险工具需要审批 — 若无 handler 则拒绝
        if handler is None:
            raise ApprovalRejectedError(
                tool_name=tool_name,
                reason="auto-edit mode: risky tool requires approval but no ApprovalHandler provided",
            )
        decision = await handler.request_approval(
            run_context=run_context,
            action_type="tool_call",
            action_detail={"tool_name": tool_name, "arguments": arguments, "risk": "high"},
        )
        if decision == ApprovalDecision.REJECTED:
            raise ApprovalRejectedError(tool_name=tool_name, reason="rejected by approver")
        if decision == ApprovalDecision.TIMEOUT:
            raise ApprovalRejectedError(tool_name=tool_name, reason="approval timed out")
        return
    # suggest 模式: 必须有 handler
    if handler is None:
        raise ApprovalRejectedError(
            tool_name=tool_name,
            reason="suggest mode requires an ApprovalHandler but none was provided",
        )
    decision = await handler.request_approval(
        run_context=run_context,
        action_type="tool_call",
        action_detail={"tool_name": tool_name, "arguments": arguments},
    )
    if decision == ApprovalDecision.REJECTED:
        raise ApprovalRejectedError(tool_name=tool_name, reason="rejected by approver")
    if decision == ApprovalDecision.TIMEOUT:
        raise ApprovalRejectedError(tool_name=tool_name, reason="approval timed out")


async def _execute_tool_calls(
    agent: Agent,
    tool_calls: list[ToolCall],
    messages: list[Message],
    tracing: _TracingCtx | None = None,
    *,
    run_context: RunContext | None = None,
    approval_handler: ApprovalHandler | None = None,
    approval_mode: ApprovalMode = ApprovalMode.FULL_AUTO,
    config: RunConfig | None = None,
) -> tuple[Agent, Handoff | None] | None:
    """执行一组工具调用（并行），将结果追加到 messages。返回 (目标 Agent, Handoff 配置) 或 None。

    LLM 返回多个 tool_calls 时，普通工具使用 asyncio.TaskGroup 并行执行。若其中包含
    Handoff 工具，Handoff 之前的普通工具并行执行完成后再处理 Handoff 控制权转移。

    超时优先级：FunctionTool.timeout > RunConfig.tool_timeout > 无限。
    """
    # 合并 Agent 级 + RunConfig 级 tool guardrails
    _merged_tool_guardrails = agent.tool_guardrails + (config.tool_guardrails if config else [])
    _hooks = config.hooks if config and config.hooks else None
    _tool_timeout = config.tool_timeout if config else None
    _max_concurrency = config.max_tool_concurrency if config else None

    # ── 1. 找到首个 Handoff 调用，分割出需要并行执行的普通工具 ──
    handoff_idx: int | None = None
    handoff_info: tuple[ToolCall, Agent, Handoff | None] | None = None
    for i, tc in enumerate(tool_calls):
        handoff_result = _find_handoff_target(agent, tc.name)
        if handoff_result is not None:
            target_agent, handoff_config = handoff_result
            handoff_idx = i
            handoff_info = (tc, target_agent, handoff_config)
            break

    normal_tool_calls = tool_calls[:handoff_idx] if handoff_idx is not None else tool_calls

    # ── 2. 单个工具执行（含 guardrails + tracing + approval + timeout）──
    tool_results: dict[str, Message] = {}

    async def _run_one(tc: ToolCall) -> None:
        """执行单个工具调用，结果写入 tool_results[tc.id]。"""
        tool = _find_tool(agent, tc.name)
        if tool is None:
            error_msg = f"Tool '{tc.name}' not found in agent '{agent.name}'"
            logger.warning(error_msg)
            tool_results[tc.id] = tool_result_to_message(tc.id, f"Error: {error_msg}", agent.name)
            return

        # 解析参数
        try:
            arguments = json.loads(tc.arguments) if tc.arguments else {}
        except json.JSONDecodeError:
            arguments = {}

        # Tool Guardrail (before): 执行前检测参数
        if _merged_tool_guardrails and run_context is not None:
            for tg in _merged_tool_guardrails:
                if tg.before_fn is None:
                    continue
                g_span = None
                if tracing and tracing.active:
                    g_span = Span(
                        trace_id=tracing.trace.trace_id if tracing.trace else "",
                        parent_span_id=tracing._agent_span.span_id if tracing._agent_span else None,
                        type=SpanType.GUARDRAIL,
                        name=tg.name,
                        status=SpanStatus.RUNNING,
                    )
                    if tracing.trace:
                        tracing.trace.spans.append(g_span)
                    for p in tracing.processors:
                        await p.on_span_start(g_span)

                try:
                    g_result = await tg.before_fn(run_context, tc.name, arguments)
                except Exception as e:
                    logger.exception("Tool guardrail '%s' before_fn raised: %s", tg.name, e)
                    g_result = GuardrailResult(tripwire_triggered=True, message=f"Guardrail error: {e}")

                g_meta = {
                    "guardrail_name": tg.name,
                    "guardrail_type": "tool_before",
                    "triggered": g_result.tripwire_triggered,
                    "message": g_result.message,
                    "tool_name": tc.name,
                }
                if g_span and tracing:
                    g_span.metadata = g_meta
                    g_status = SpanStatus.COMPLETED if not g_result.tripwire_triggered else SpanStatus.FAILED
                    await tracing.end_span(g_span, output=g_result.message, status=g_status)

                if g_result.tripwire_triggered:
                    blocked_msg = f"Tool guardrail '{tg.name}' blocked: {g_result.message}"
                    tool_results[tc.id] = tool_result_to_message(tc.id, f"Error: {blocked_msg}", agent.name)
                    return

        # 执行工具（带 Tracing + Approval + Timeout）
        tool_span = await tracing.start_tool_span(tc.name, arguments) if tracing else None
        if _hooks and run_context:
            await _invoke_hook(_hooks.on_tool_start, "on_tool_start", run_context, tc.name, arguments)
        try:
            if run_context is not None:
                await _check_approval(
                    run_context, approval_handler, approval_mode, tc.name, arguments,
                    tool_approval_required=getattr(tool, "approval_required", False),
                )
            # 超时优先级: tool.timeout（工具内部已处理）> RunConfig.tool_timeout > 无限
            if tool.timeout is None and _tool_timeout is not None:
                result = await asyncio.wait_for(tool.execute(arguments), timeout=_tool_timeout)
            else:
                result = await tool.execute(arguments)
        except asyncio.TimeoutError:
            timeout_val = tool.timeout or _tool_timeout
            error_result = f"Error: Tool '{tc.name}' timed out after {timeout_val}s."
            tool_results[tc.id] = tool_result_to_message(tc.id, error_result, agent.name)
            if tool_span:
                await tracing.end_span(tool_span, output=error_result, status=SpanStatus.FAILED)
            return
        except Exception as e:
            error_result = f"Error: {e}"
            tool_results[tc.id] = tool_result_to_message(tc.id, error_result, agent.name)
            if tool_span:
                await tracing.end_span(tool_span, output=error_result, status=SpanStatus.FAILED)
            return

        # Tool Guardrail (after): 执行后检测返回值
        if _merged_tool_guardrails and run_context is not None:
            for tg in _merged_tool_guardrails:
                if tg.after_fn is None:
                    continue
                g_span = None
                if tracing and tracing.active:
                    g_span = Span(
                        trace_id=tracing.trace.trace_id if tracing.trace else "",
                        parent_span_id=tracing._agent_span.span_id if tracing._agent_span else None,
                        type=SpanType.GUARDRAIL,
                        name=tg.name,
                        status=SpanStatus.RUNNING,
                    )
                    if tracing.trace:
                        tracing.trace.spans.append(g_span)
                    for p in tracing.processors:
                        await p.on_span_start(g_span)

                try:
                    g_result = await tg.after_fn(run_context, tc.name, result)
                except Exception as e:
                    logger.exception("Tool guardrail '%s' after_fn raised: %s", tg.name, e)
                    g_result = GuardrailResult(tripwire_triggered=True, message=f"Guardrail error: {e}")

                g_meta = {
                    "guardrail_name": tg.name,
                    "guardrail_type": "tool_after",
                    "triggered": g_result.tripwire_triggered,
                    "message": g_result.message,
                    "tool_name": tc.name,
                }
                if g_span and tracing:
                    g_span.metadata = g_meta
                    g_status = SpanStatus.COMPLETED if not g_result.tripwire_triggered else SpanStatus.FAILED
                    await tracing.end_span(g_span, output=g_result.message, status=g_status)

                if g_result.tripwire_triggered:
                    result = f"Error: Tool guardrail '{tg.name}' blocked result: {g_result.message}"
                    break

        # Hooks: on_tool_end
        if _hooks and run_context:
            await _invoke_hook(_hooks.on_tool_end, "on_tool_end", run_context, tc.name, result)
        tool_results[tc.id] = tool_result_to_message(tc.id, result, agent.name)
        if tool_span:
            await tracing.end_span(tool_span, output=result)

    # ── 3. 并行执行所有普通工具（支持并发限流）──────────────────────────────
    if len(normal_tool_calls) == 1:
        await _run_one(normal_tool_calls[0])
    elif normal_tool_calls:
        if _max_concurrency is not None and _max_concurrency > 0:
            _semaphore = asyncio.Semaphore(_max_concurrency)

            async def _run_one_limited(tc: ToolCall) -> None:
                """使用 Semaphore 限流的工具执行包装。"""
                async with _semaphore:
                    await _run_one(tc)

            async with asyncio.TaskGroup() as tg:
                for tc in normal_tool_calls:
                    tg.create_task(_run_one_limited(tc))
        else:
            async with asyncio.TaskGroup() as tg:
                for tc in normal_tool_calls:
                    tg.create_task(_run_one(tc))

    # 按原始 tool_call 顺序追加结果到 messages
    for tc in normal_tool_calls:
        if tc.id in tool_results:
            messages.append(tool_results[tc.id])

    # ── 4. 处理 Handoff（如有）──────────────────────────────
    if handoff_info:
        tc, target_agent, handoff_config = handoff_info
        if _hooks and run_context:
            await _invoke_hook(_hooks.on_handoff, "on_handoff", run_context, agent.name, target_agent.name)
        messages.append(tool_result_to_message(tc.id, "", agent.name))
        if tracing:
            await tracing.handoff_span(agent.name, target_agent.name)
        return (target_agent, handoff_config)

    return None


class _TracingCtx:
    """Runner 内部 Tracing 上下文管理器。tracing_enabled=False 时所有操作为 noop。"""

    def __init__(self, config: RunConfig, agent_name: str) -> None:
        self._enabled = config.tracing_enabled
        self.processors: list[TraceProcessor] = config.trace_processors if self._enabled else []
        self.include_sensitive = config.trace_include_sensitive_data
        self.trace: Trace | None = None
        self._agent_span: Span | None = None
        self._agent_name = agent_name

    @property
    def active(self) -> bool:
        return self._enabled

    async def start_trace(self, workflow_name: str) -> None:
        if not self.active:
            return
        self.trace = Trace(workflow_name=workflow_name)
        for p in self.processors:
            await p.on_trace_start(self.trace)

    async def end_trace(self) -> Trace | None:
        if not self.active or self.trace is None:
            return None
        self.trace.end_time = datetime.now(timezone.utc)
        for p in self.processors:
            await p.on_trace_end(self.trace)
        return self.trace

    async def start_agent_span(self, agent_name: str) -> Span:
        span = Span(
            trace_id=self.trace.trace_id if self.trace else "",
            type=SpanType.AGENT,
            name=agent_name,
            status=SpanStatus.RUNNING,
        )
        if self.trace:
            self.trace.spans.append(span)
        self._agent_span = span
        self._agent_name = agent_name
        for p in self.processors:
            await p.on_span_start(span)
        return span

    async def start_llm_span(self, model: str, input_messages: list[Message] | None = None) -> Span:
        span = Span(
            trace_id=self.trace.trace_id if self.trace else "",
            parent_span_id=self._agent_span.span_id if self._agent_span else None,
            type=SpanType.LLM,
            name=model,
            status=SpanStatus.RUNNING,
            model=model,
        )
        if self.include_sensitive and input_messages:
            span.input = [{"role": m.role.value, "content": m.content[:500] if m.content else ""} for m in input_messages[-5:]]
        if self.trace:
            self.trace.spans.append(span)
        for p in self.processors:
            await p.on_span_start(span)
        return span

    async def start_tool_span(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Span:
        span = Span(
            trace_id=self.trace.trace_id if self.trace else "",
            parent_span_id=self._agent_span.span_id if self._agent_span else None,
            type=SpanType.TOOL,
            name=tool_name,
            status=SpanStatus.RUNNING,
        )
        if self.include_sensitive and arguments:
            span.input = arguments
        if self.trace:
            self.trace.spans.append(span)
        for p in self.processors:
            await p.on_span_start(span)
        return span

    async def handoff_span(self, from_agent: str, to_agent: str) -> Span:
        span = Span(
            trace_id=self.trace.trace_id if self.trace else "",
            parent_span_id=self._agent_span.span_id if self._agent_span else None,
            type=SpanType.HANDOFF,
            name=f"{from_agent} → {to_agent}",
            status=SpanStatus.COMPLETED,
        )
        span.end_time = datetime.now(timezone.utc)
        span.metadata = {"from": from_agent, "to": to_agent}
        if self.trace:
            self.trace.spans.append(span)
        for p in self.processors:
            await p.on_span_start(span)
            await p.on_span_end(span)
        return span

    async def end_span(
        self,
        span: Span,
        output: Any = None,
        status: SpanStatus = SpanStatus.COMPLETED,
        token_usage: TokenUsage | None = None,
    ) -> None:
        span.end_time = datetime.now(timezone.utc)
        span.status = status
        if self.include_sensitive and output is not None:
            span.output = str(output)[:1000] if isinstance(output, str) else output
        if token_usage:
            span.token_usage = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }
        for p in self.processors:
            await p.on_span_end(span)


class Runner:
    """Agent 执行引擎。驱动 Agent Loop 完成推理和工具调用。"""

    @staticmethod
    async def run(
        agent: Agent,
        input: str | list[Message],
        *,
        session: Session | None = None,
        config: RunConfig | None = None,
        context: dict[str, Any] | None = None,
        max_turns: int = 10,
    ) -> RunResult:
        """异步运行 Agent，返回最终结果。

        Agent Loop 核心流程：
        1. 构建 system message + 用户输入
        2. 调用 LLM
        3. 若 LLM 返回 tool_calls → 执行工具 → 回到步骤 2
        4. 若 LLM 返回纯文本 → 循环结束
        5. 若检测到 Handoff → 切换 Agent → 回到步骤 1

        若提供 session，自动加载历史消息并在结束后保存新增消息。
        """
        config = config or RunConfig()
        provider = _resolve_provider(config)
        total_usage = TokenUsage()
        approval_mode = _resolve_approval_mode(agent, config)
        approval_handler = config.approval_handler

        # Tracing 上下文
        tracing = _TracingCtx(config, agent.name)
        if tracing.active:
            await tracing.start_trace(config.workflow_name)

        # 初始化消息历史
        messages = _normalize_input(input)
        current_agent = agent
        turn_count = 0

        # Session: 加载历史消息
        history_offset = 0
        if session is not None:
            history = await session.get_history()
            if history:
                # 自动裁剪历史以适配 Context Window
                trim_config = _build_trim_config(config)
                if trim_config is not None:
                    history = HistoryTrimmer.trim(history, trim_config)
                messages = history + messages
                history_offset = len(history)

        # Input Guardrails: 首次执行前检测用户输入
        _merged_input_guardrails = current_agent.input_guardrails + config.input_guardrails
        if _merged_input_guardrails:
            user_text = ""
            for msg in reversed(messages):
                if msg.role == MessageRole.USER and msg.content:
                    user_text = msg.content
                    break
            guardrail_ctx = RunContext(
                agent=current_agent,
                config=config,
                context=context or {},
                turn_count=0,
            )
            try:
                await _execute_input_guardrails(
                    _merged_input_guardrails,
                    guardrail_ctx,
                    user_text,
                    tracing=tracing if tracing.active else None,
                    parallel=config.guardrail_parallel if config else False,
                )
            except InputGuardrailTripwireError:
                trace = await tracing.end_trace()
                if session is not None:
                    await session.append(messages[history_offset:])
                raise

        # Hooks
        hooks = config.hooks
        # Hooks: on_run_start
        if hooks:
            _start_ctx = RunContext(agent=current_agent, config=config, context=context or {}, turn_count=0)
            await _invoke_hook(hooks.on_run_start, "on_run_start", _start_ctx)

        while turn_count < max_turns:
            turn_count += 1

            # 构建 RunContext
            run_ctx = RunContext(
                agent=current_agent,
                config=config,
                context=context or {},
                turn_count=turn_count,
            )

            # Tracing: Agent Span
            agent_span = await tracing.start_agent_span(current_agent.name) if tracing.active else None

            # Hooks: on_agent_start
            if hooks:
                await _invoke_hook(hooks.on_agent_start, "on_agent_start", run_ctx, current_agent.name)

            # 准备 LLM 调用参数
            system_msg = await _build_system_message(current_agent, run_ctx)
            llm_messages: list[Message] = []
            if system_msg.content:
                llm_messages.append(system_msg)
            llm_messages.extend(messages)
            tool_schemas = _build_tool_schemas(current_agent, run_ctx)

            model_name = _resolve_model(current_agent, config)
            settings = _resolve_settings(current_agent, config)
            response_format = _build_response_format(current_agent.output_type)

            # Tracing: LLM Span
            llm_span = await tracing.start_llm_span(model_name, llm_messages) if tracing.active else None

            # Hooks: on_llm_start
            if hooks:
                await _invoke_hook(hooks.on_llm_start, "on_llm_start", run_ctx, model_name, llm_messages)

            # 调用 LLM（含重试逻辑）
            _max_retries = config.max_retries
            _retry_delay = config.retry_delay
            _last_error: Exception | None = None
            for _attempt in range(_max_retries + 1):
                try:
                    response: ModelResponse = await provider.chat(
                        model=model_name,
                        messages=llm_messages,
                        settings=settings,
                        tools=tool_schemas or None,
                        stream=False,
                        response_format=response_format,
                    )  # type: ignore[assignment]
                    _last_error = None
                    break
                except Exception as e:
                    _last_error = e
                    if _attempt < _max_retries:
                        delay = _retry_delay * (2 ** _attempt)
                        logger.warning(
                            "LLM call failed for agent '%s' (attempt %d/%d), retrying in %.1fs: %s",
                            current_agent.name, _attempt + 1, _max_retries + 1, delay, e,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception("LLM call failed for agent '%s' after %d attempts", current_agent.name, _max_retries + 1)

            if _last_error is not None:
                if llm_span:
                    await tracing.end_span(llm_span, output=str(_last_error), status=SpanStatus.FAILED)
                if agent_span:
                    await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                # Hooks: on_error + on_agent_end
                if hooks:
                    await _invoke_hook(hooks.on_error, "on_error", run_ctx, _last_error)
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                trace = await tracing.end_trace()
                # Session: 异常时也保存已有消息
                if session is not None:
                    await session.append(messages[history_offset:])
                _err_result = RunResult(
                    output=f"Error: LLM call failed: {_last_error}",
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )
                # Hooks: on_run_end
                if hooks:
                    await _invoke_hook(hooks.on_run_end, "on_run_end", run_ctx, _err_result)
                return _err_result

            _accumulate_usage(total_usage, response.token_usage)

            # Tracing: 结束 LLM Span
            if llm_span:
                await tracing.end_span(llm_span, output=response.content, token_usage=response.token_usage)

            # Hooks: on_llm_end
            if hooks:
                await _invoke_hook(hooks.on_llm_end, "on_llm_end", run_ctx, response)

            # 将 LLM 回复追加到历史
            assistant_msg = model_response_to_assistant_message(response, current_agent.name)
            messages.append(assistant_msg)

            # 无工具调用 → 最终输出
            if not response.tool_calls:
                raw_output = response.content or ""
                # 结构化输出解析
                final_output: Any = _parse_structured_output(raw_output, current_agent.output_type)

                # Output Guardrails: final_output 后检测（使用原始文本）
                _merged_output_guardrails = current_agent.output_guardrails + config.output_guardrails
                if _merged_output_guardrails:
                    try:
                        await _execute_output_guardrails(
                            _merged_output_guardrails,
                            run_ctx,
                            raw_output,
                            tracing=tracing if tracing.active else None,
                            parallel=config.guardrail_parallel if config else False,
                        )
                    except OutputGuardrailTripwireError:
                        if agent_span:
                            await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                        trace = await tracing.end_trace()
                        if session is not None:
                            await session.append(messages[history_offset:])
                        raise

                # Hooks: on_agent_end
                if hooks:
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                if agent_span:
                    await tracing.end_span(agent_span, output=raw_output)
                trace = await tracing.end_trace()
                # Session: 保存新增消息
                if session is not None:
                    await session.append(messages[history_offset:])
                _ok_result = RunResult(
                    output=final_output,
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )
                # Hooks: on_run_end
                if hooks:
                    await _invoke_hook(hooks.on_run_end, "on_run_end", run_ctx, _ok_result)
                return _ok_result

            # 执行工具调用
            handoff_result = await _execute_tool_calls(
                current_agent, response.tool_calls, messages,
                tracing=tracing if tracing.active else None,
                run_context=run_ctx,
                approval_handler=approval_handler,
                approval_mode=approval_mode,
                config=config,
            )

            # Handoff: 切换 Agent，不增加 turn_count
            if handoff_result is not None:
                target_agent, handoff_config = handoff_result
                logger.info("Handoff: %s → %s", current_agent.name, target_agent.name)
                # Hooks: on_agent_end (handoff 旧 Agent)
                if hooks:
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                if agent_span:
                    await tracing.end_span(agent_span)
                # 应用 InputFilter
                if handoff_config and handoff_config.input_filter:
                    messages = handoff_config.input_filter(messages)
                current_agent = target_agent
                turn_count -= 1  # Handoff 本身不算一轮
            # 非 Handoff 工具调用：结束 agent span 并在下一轮重建
            elif agent_span:
                await tracing.end_span(agent_span)

        # 超过 max_turns
        logger.warning("Agent loop exceeded max_turns=%d", max_turns)
        last_content = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.ASSISTANT and msg.content:
                last_content = msg.content
                break

        trace = await tracing.end_trace()

        # Session: 保存新增消息
        if session is not None:
            await session.append(messages[history_offset:])

        _max_result = RunResult(
            output=last_content,
            messages=messages,
            last_agent_name=current_agent.name,
            token_usage=total_usage,
            turn_count=turn_count,
            trace=trace,
        )
        # Hooks: on_run_end
        if hooks:
            _max_ctx = RunContext(agent=current_agent, config=config, context=context or {}, turn_count=turn_count)
            await _invoke_hook(hooks.on_run_end, "on_run_end", _max_ctx, _max_result)
        return _max_result

    @staticmethod
    def run_sync(
        agent: Agent,
        input: str | list[Message],
        **kwargs: Any,
    ) -> RunResult:
        """同步运行。兼容已有事件循环（如 Jupyter notebook）。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, Runner.run(agent, input, **kwargs))
                return future.result()
        return asyncio.run(Runner.run(agent, input, **kwargs))

    @staticmethod
    async def run_streamed(
        agent: Agent,
        input: str | list[Message],
        *,
        session: Session | None = None,
        config: RunConfig | None = None,
        context: dict[str, Any] | None = None,
        max_turns: int = 10,
    ) -> AsyncIterator[StreamEvent]:
        """异步流式运行。逐步产出 StreamEvent。

        与 run() 相同的 Agent Loop，但 LLM 响应以流式 chunk 产出。
        若提供 session，自动加载历史消息并在结束后保存新增消息。
        """
        config = config or RunConfig()
        provider = _resolve_provider(config)
        total_usage = TokenUsage()
        messages = _normalize_input(input)
        current_agent = agent
        turn_count = 0
        approval_mode = _resolve_approval_mode(agent, config)
        approval_handler = config.approval_handler

        # Tracing 上下文
        tracing = _TracingCtx(config, agent.name)
        if tracing.active:
            await tracing.start_trace(config.workflow_name)

        # Session: 加载历史消息
        history_offset = 0
        if session is not None:
            history = await session.get_history()
            if history:
                # 自动裁剪历史以适配 Context Window
                trim_config = _build_trim_config(config)
                if trim_config is not None:
                    history = HistoryTrimmer.trim(history, trim_config)
                messages = history + messages
                history_offset = len(history)

        # Input Guardrails: 首次执行前检测用户输入
        _merged_input_guardrails = current_agent.input_guardrails + config.input_guardrails
        if _merged_input_guardrails:
            user_text = ""
            for msg in reversed(messages):
                if msg.role == MessageRole.USER and msg.content:
                    user_text = msg.content
                    break
            guardrail_ctx = RunContext(
                agent=current_agent,
                config=config,
                context=context or {},
                turn_count=0,
            )
            try:
                await _execute_input_guardrails(
                    _merged_input_guardrails,
                    guardrail_ctx,
                    user_text,
                    tracing=tracing if tracing.active else None,
                    parallel=config.guardrail_parallel if config else False,
                )
            except InputGuardrailTripwireError:
                await tracing.end_trace()
                if session is not None:
                    await session.append(messages[history_offset:])
                raise

        # Hooks
        hooks = config.hooks
        # Hooks: on_run_start
        if hooks:
            _start_ctx = RunContext(agent=current_agent, config=config, context=context or {}, turn_count=0)
            await _invoke_hook(hooks.on_run_start, "on_run_start", _start_ctx)

        while turn_count < max_turns:
            turn_count += 1

            run_ctx = RunContext(
                agent=current_agent,
                config=config,
                context=context or {},
                turn_count=turn_count,
            )

            yield StreamEvent(type=StreamEventType.AGENT_START, agent_name=current_agent.name)

            # Tracing: Agent Span
            agent_span = await tracing.start_agent_span(current_agent.name) if tracing.active else None

            # Hooks: on_agent_start
            if hooks:
                await _invoke_hook(hooks.on_agent_start, "on_agent_start", run_ctx, current_agent.name)

            system_msg = await _build_system_message(current_agent, run_ctx)
            llm_messages: list[Message] = []
            if system_msg.content:
                llm_messages.append(system_msg)
            llm_messages.extend(messages)
            tool_schemas = _build_tool_schemas(current_agent, run_ctx)

            model_name = _resolve_model(current_agent, config)
            settings = _resolve_settings(current_agent, config)
            response_format = _build_response_format(current_agent.output_type)

            # Tracing: LLM Span
            llm_span = await tracing.start_llm_span(model_name, llm_messages) if tracing.active else None

            # Hooks: on_llm_start
            if hooks:
                await _invoke_hook(hooks.on_llm_start, "on_llm_start", run_ctx, model_name, llm_messages)

            # 流式调用 LLM（含重试逻辑）
            _max_retries_s = config.max_retries
            _retry_delay_s = config.retry_delay
            _last_error_s: Exception | None = None
            stream = None
            for _attempt_s in range(_max_retries_s + 1):
                try:
                    stream = await provider.chat(
                        model=model_name,
                        messages=llm_messages,
                        settings=settings,
                        tools=tool_schemas or None,
                        stream=True,
                        response_format=response_format,
                    )
                    _last_error_s = None
                    break
                except Exception as e:
                    _last_error_s = e
                    if _attempt_s < _max_retries_s:
                        delay = _retry_delay_s * (2 ** _attempt_s)
                        logger.warning(
                            "LLM stream call failed for agent '%s' (attempt %d/%d), retrying in %.1fs: %s",
                            current_agent.name, _attempt_s + 1, _max_retries_s + 1, delay, e,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception("LLM stream call failed for agent '%s' after %d attempts", current_agent.name, _max_retries_s + 1)

            if _last_error_s is not None:
                if llm_span:
                    await tracing.end_span(llm_span, output=str(_last_error_s), status=SpanStatus.FAILED)
                if agent_span:
                    await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                # Hooks: on_error + on_agent_end
                if hooks:
                    await _invoke_hook(hooks.on_error, "on_error", run_ctx, _last_error_s)
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                trace = await tracing.end_trace()
                # Session: 异常时也保存已有消息
                if session is not None:
                    await session.append(messages[history_offset:])
                _err_result = RunResult(
                    output=f"Error: LLM call failed: {_last_error_s}",
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )
                # Hooks: on_run_end
                if hooks:
                    await _invoke_hook(hooks.on_run_end, "on_run_end", run_ctx, _err_result)
                yield StreamEvent(
                    type=StreamEventType.RUN_COMPLETE,
                    data=_err_result,
                )
                return

            # 聚合流式响应
            full_content = ""
            tool_call_buffers: dict[int, dict[str, str]] = {}

            async for chunk in stream:  # type: ignore[union-attr]
                if chunk.content:
                    full_content += chunk.content
                    yield StreamEvent(
                        type=StreamEventType.LLM_CHUNK,
                        data=chunk.content,
                        agent_name=current_agent.name,
                    )

                for tc_chunk in chunk.tool_call_chunks:
                    buf = tool_call_buffers.setdefault(tc_chunk.index, {"id": "", "name": "", "arguments": ""})
                    if tc_chunk.id:
                        buf["id"] = tc_chunk.id
                    if tc_chunk.name:
                        buf["name"] = tc_chunk.name
                    buf["arguments"] += tc_chunk.arguments_delta

            # 组装完整 tool_calls
            aggregated_tool_calls: list[ToolCall] = []
            for _idx in sorted(tool_call_buffers):
                buf = tool_call_buffers[_idx]
                aggregated_tool_calls.append(ToolCall(id=buf["id"], name=buf["name"], arguments=buf["arguments"]))

            # 构建完整的 ModelResponse 用于消息历史
            aggregated_response = ModelResponse(
                content=full_content or None,
                tool_calls=aggregated_tool_calls,
            )
            assistant_msg = model_response_to_assistant_message(aggregated_response, current_agent.name)
            messages.append(assistant_msg)

            # Hooks: on_llm_end
            if hooks:
                await _invoke_hook(hooks.on_llm_end, "on_llm_end", run_ctx, aggregated_response)

            if not aggregated_tool_calls:
                raw_output = full_content
                # 结构化输出解析
                final_output: Any = _parse_structured_output(raw_output, current_agent.output_type)

                # Output Guardrails: final_output 后检测（流式，使用原始文本）
                _merged_output_guardrails = current_agent.output_guardrails + config.output_guardrails
                if _merged_output_guardrails:
                    try:
                        await _execute_output_guardrails(
                            _merged_output_guardrails,
                            run_ctx,
                            raw_output,
                            tracing=tracing if tracing.active else None,
                            parallel=config.guardrail_parallel if config else False,
                        )
                    except OutputGuardrailTripwireError:
                        if llm_span:
                            await tracing.end_span(llm_span, output=raw_output)
                        if agent_span:
                            await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                        trace = await tracing.end_trace()
                        if session is not None:
                            await session.append(messages[history_offset:])
                        raise

                # Tracing: 结束 LLM + Agent Span
                if llm_span:
                    await tracing.end_span(llm_span, output=raw_output)
                # Hooks: on_agent_end
                if hooks:
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                if agent_span:
                    await tracing.end_span(agent_span, output=raw_output)
                trace = await tracing.end_trace()
                # Session: 保存新增消息
                if session is not None:
                    await session.append(messages[history_offset:])
                _ok_result = RunResult(
                    output=final_output,
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )
                # Hooks: on_run_end
                if hooks:
                    await _invoke_hook(hooks.on_run_end, "on_run_end", run_ctx, _ok_result)
                yield StreamEvent(type=StreamEventType.AGENT_END, agent_name=current_agent.name)
                yield StreamEvent(
                    type=StreamEventType.RUN_COMPLETE,
                    data=_ok_result,
                )
                return

            # 执行工具调用
            for tc in aggregated_tool_calls:
                yield StreamEvent(
                    type=StreamEventType.TOOL_CALL_START,
                    data={"tool": tc.name, "arguments": tc.arguments},
                    agent_name=current_agent.name,
                )

            # Tracing: 结束 LLM Span（流式聚合完成后）
            if llm_span:
                await tracing.end_span(llm_span, output=full_content)

            handoff_result = await _execute_tool_calls(
                current_agent, aggregated_tool_calls, messages,
                tracing=tracing if tracing.active else None,
                run_context=run_ctx,
                approval_handler=approval_handler,
                approval_mode=approval_mode,
                config=config,
            )

            for tc in aggregated_tool_calls:
                yield StreamEvent(
                    type=StreamEventType.TOOL_CALL_END,
                    data={"tool": tc.name},
                    agent_name=current_agent.name,
                )

            if handoff_result is not None:
                target_agent, handoff_config = handoff_result
                yield StreamEvent(
                    type=StreamEventType.HANDOFF,
                    data={"from": current_agent.name, "to": target_agent.name},
                    agent_name=current_agent.name,
                )
                # Hooks: on_agent_end (handoff 旧 Agent)
                if hooks:
                    await _invoke_hook(hooks.on_agent_end, "on_agent_end", run_ctx, current_agent.name)
                if agent_span:
                    await tracing.end_span(agent_span)
                # 应用 InputFilter
                if handoff_config and handoff_config.input_filter:
                    messages = handoff_config.input_filter(messages)
                current_agent = target_agent
                turn_count -= 1
            elif agent_span:
                await tracing.end_span(agent_span)

        # 超过 max_turns
        last_content = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.ASSISTANT and msg.content:
                last_content = msg.content
                break

        trace = await tracing.end_trace()

        # Session: 保存新增消息
        if session is not None:
            await session.append(messages[history_offset:])

        _max_result = RunResult(
            output=last_content,
            messages=messages,
            last_agent_name=current_agent.name,
            token_usage=total_usage,
            turn_count=turn_count,
            trace=trace,
        )
        # Hooks: on_run_end
        if hooks:
            _max_ctx = RunContext(agent=current_agent, config=config, context=context or {}, turn_count=turn_count)
            await _invoke_hook(hooks.on_run_end, "on_run_end", _max_ctx, _max_result)
        yield StreamEvent(
            type=StreamEventType.RUN_COMPLETE,
            data=_max_result,
        )
