"""Runner — Agent 执行引擎，驱动 Agent Loop 完成推理和工具调用。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.approval.handler import ApprovalHandler
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError
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
from ckyclaw_framework.runner.result import RunResult, StreamEvent, StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType
from ckyclaw_framework.tracing.trace import Trace

logger = logging.getLogger(__name__)

# Handoff 工具名前缀约定
_HANDOFF_TOOL_PREFIX = "transfer_to_"


def _build_system_message(agent: Agent, run_context: RunContext) -> Message:
    """构建 system 消息，注入 Agent instructions。"""
    if callable(agent.instructions):
        text = agent.instructions(run_context)
    else:
        text = agent.instructions or ""
    return Message(role=MessageRole.SYSTEM, content=text)


def _build_tool_schemas(agent: Agent) -> list[dict[str, Any]]:
    """从 Agent 的 tools + handoffs 构建 OpenAI tool schemas。"""
    schemas: list[dict[str, Any]] = []
    for tool in agent.tools:
        schemas.append(tool.to_openai_schema())
    # Handoff 生成特殊工具
    for target in agent.handoffs:
        if isinstance(target, Handoff):
            tool_name = target.resolved_tool_name
            description = target.resolved_tool_description
        else:
            tool_name = f"{_HANDOFF_TOOL_PREFIX}{target.name}"
            description = f"Transfer conversation to {target.name}: {target.description}"
        schemas.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {"type": "object", "properties": {}},
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
) -> None:
    """执行 Input Guardrails（阻塞模式）。

    按列表顺序依次执行。首个 Tripwire 触发后立即中断（短路）。
    触发时抛出 InputGuardrailTripwireError。
    """
    for guardrail in guardrails:
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
) -> None:
    """检查工具调用是否需要审批。需要时调用 handler 并处理结果。

    full-auto: 直接返回（不审批）。
    suggest: 所有工具调用需审批。
    auto-edit: MVP 阶段等同 full-auto（待 RiskClassifier 实现）。
    """
    if mode == ApprovalMode.FULL_AUTO:
        return
    if mode == ApprovalMode.AUTO_EDIT:
        # MVP: auto-edit 暂等同 full-auto，后续加 RiskClassifier
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
) -> tuple[Agent, Handoff | None] | None:
    """执行一组工具调用，将结果追加到 messages。返回 (目标 Agent, Handoff 配置) 或 None。

    注意：若同一轮中 LLM 同时返回 Handoff 工具和普通工具，Handoff 之前的普通工具
    会正常执行，但 Handoff 之后的工具将被跳过（控制权已转移）。
    """
    for tc in tool_calls:
        # 检查 Handoff
        handoff_result = _find_handoff_target(agent, tc.name)
        if handoff_result is not None:
            target_agent, handoff_config = handoff_result
            # Handoff 工具"执行结果"是空的，控制权转移
            messages.append(tool_result_to_message(tc.id, "", agent.name))
            if tracing:
                await tracing.handoff_span(agent.name, target_agent.name)
            return (target_agent, handoff_config)

        # 查找普通工具
        tool = _find_tool(agent, tc.name)
        if tool is None:
            error_msg = f"Tool '{tc.name}' not found in agent '{agent.name}'"
            logger.warning(error_msg)
            messages.append(tool_result_to_message(tc.id, f"Error: {error_msg}", agent.name))
            continue

        # 解析参数
        try:
            arguments = json.loads(tc.arguments) if tc.arguments else {}
        except json.JSONDecodeError:
            arguments = {}

        # 执行工具（带 Tracing + Approval 检查）
        tool_span = await tracing.start_tool_span(tc.name, arguments) if tracing else None
        try:
            # Approval: 在执行前检查审批
            if run_context is not None:
                await _check_approval(run_context, approval_handler, approval_mode, tc.name, arguments)
            result = await tool.execute(arguments)
            messages.append(tool_result_to_message(tc.id, result, agent.name))
            if tool_span:
                await tracing.end_span(tool_span, output=result)
        except Exception as e:
            error_result = f"Error: {e}"
            messages.append(tool_result_to_message(tc.id, error_result, agent.name))
            if tool_span:
                await tracing.end_span(tool_span, output=error_result, status=SpanStatus.FAILED)

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
                messages = history + messages
                history_offset = len(history)

        # Input Guardrails: 首次执行前检测用户输入
        if current_agent.input_guardrails:
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
                    current_agent.input_guardrails,
                    guardrail_ctx,
                    user_text,
                    tracing=tracing if tracing.active else None,
                )
            except InputGuardrailTripwireError:
                trace = await tracing.end_trace()
                if session is not None:
                    await session.append(messages[history_offset:])
                raise

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

            # 准备 LLM 调用参数
            system_msg = _build_system_message(current_agent, run_ctx)
            llm_messages: list[Message] = []
            if system_msg.content:
                llm_messages.append(system_msg)
            llm_messages.extend(messages)
            tool_schemas = _build_tool_schemas(current_agent)

            model_name = _resolve_model(current_agent, config)
            settings = _resolve_settings(current_agent, config)

            # Tracing: LLM Span
            llm_span = await tracing.start_llm_span(model_name, llm_messages) if tracing.active else None

            # 调用 LLM
            try:
                response: ModelResponse = await provider.chat(
                    model=model_name,
                    messages=llm_messages,
                    settings=settings,
                    tools=tool_schemas or None,
                    stream=False,
                )  # type: ignore[assignment]
            except Exception as e:
                logger.exception("LLM call failed for agent '%s'", current_agent.name)
                if llm_span:
                    await tracing.end_span(llm_span, output=str(e), status=SpanStatus.FAILED)
                if agent_span:
                    await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                trace = await tracing.end_trace()
                # Session: 异常时也保存已有消息
                if session is not None:
                    await session.append(messages[history_offset:])
                return RunResult(
                    output=f"Error: LLM call failed: {e}",
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )

            _accumulate_usage(total_usage, response.token_usage)

            # Tracing: 结束 LLM Span
            if llm_span:
                await tracing.end_span(llm_span, output=response.content, token_usage=response.token_usage)

            # 将 LLM 回复追加到历史
            assistant_msg = model_response_to_assistant_message(response, current_agent.name)
            messages.append(assistant_msg)

            # 无工具调用 → 最终输出
            if not response.tool_calls:
                if agent_span:
                    await tracing.end_span(agent_span, output=response.content)
                trace = await tracing.end_trace()
                # Session: 保存新增消息
                if session is not None:
                    await session.append(messages[history_offset:])
                return RunResult(
                    output=response.content or "",
                    messages=messages,
                    last_agent_name=current_agent.name,
                    token_usage=total_usage,
                    turn_count=turn_count,
                    trace=trace,
                )

            # 执行工具调用
            handoff_result = await _execute_tool_calls(
                current_agent, response.tool_calls, messages,
                tracing=tracing if tracing.active else None,
                run_context=run_ctx,
                approval_handler=approval_handler,
                approval_mode=approval_mode,
            )

            # Handoff: 切换 Agent，不增加 turn_count
            if handoff_result is not None:
                target_agent, handoff_config = handoff_result
                logger.info("Handoff: %s → %s", current_agent.name, target_agent.name)
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

        return RunResult(
            output=last_content,
            messages=messages,
            last_agent_name=current_agent.name,
            token_usage=total_usage,
            turn_count=turn_count,
            trace=trace,
        )

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
                messages = history + messages
                history_offset = len(history)

        # Input Guardrails: 首次执行前检测用户输入
        if current_agent.input_guardrails:
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
                    current_agent.input_guardrails,
                    guardrail_ctx,
                    user_text,
                    tracing=tracing if tracing.active else None,
                )
            except InputGuardrailTripwireError:
                await tracing.end_trace()
                if session is not None:
                    await session.append(messages[history_offset:])
                raise

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

            system_msg = _build_system_message(current_agent, run_ctx)
            llm_messages: list[Message] = []
            if system_msg.content:
                llm_messages.append(system_msg)
            llm_messages.extend(messages)
            tool_schemas = _build_tool_schemas(current_agent)

            model_name = _resolve_model(current_agent, config)
            settings = _resolve_settings(current_agent, config)

            # Tracing: LLM Span
            llm_span = await tracing.start_llm_span(model_name, llm_messages) if tracing.active else None

            # 流式调用 LLM
            try:
                stream = await provider.chat(
                    model=model_name,
                    messages=llm_messages,
                    settings=settings,
                    tools=tool_schemas or None,
                    stream=True,
                )
            except Exception as e:
                logger.exception("LLM stream call failed for agent '%s'", current_agent.name)
                if llm_span:
                    await tracing.end_span(llm_span, output=str(e), status=SpanStatus.FAILED)
                if agent_span:
                    await tracing.end_span(agent_span, status=SpanStatus.FAILED)
                trace = await tracing.end_trace()
                # Session: 异常时也保存已有消息
                if session is not None:
                    await session.append(messages[history_offset:])
                yield StreamEvent(
                    type=StreamEventType.RUN_COMPLETE,
                    data=RunResult(
                        output=f"Error: LLM call failed: {e}",
                        messages=messages,
                        last_agent_name=current_agent.name,
                        token_usage=total_usage,
                        turn_count=turn_count,
                        trace=trace,
                    ),
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

            if not aggregated_tool_calls:
                # Tracing: 结束 LLM + Agent Span
                if llm_span:
                    await tracing.end_span(llm_span, output=full_content)
                if agent_span:
                    await tracing.end_span(agent_span, output=full_content)
                trace = await tracing.end_trace()
                # Session: 保存新增消息
                if session is not None:
                    await session.append(messages[history_offset:])
                yield StreamEvent(type=StreamEventType.AGENT_END, agent_name=current_agent.name)
                yield StreamEvent(
                    type=StreamEventType.RUN_COMPLETE,
                    data=RunResult(
                        output=full_content,
                        messages=messages,
                        last_agent_name=current_agent.name,
                        token_usage=total_usage,
                        turn_count=turn_count,
                        trace=trace,
                    ),
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

        yield StreamEvent(
            type=StreamEventType.RUN_COMPLETE,
            data=RunResult(
                output=last_content,
                messages=messages,
                last_agent_name=current_agent.name,
                token_usage=total_usage,
                turn_count=turn_count,
                trace=trace,
            ),
        )
