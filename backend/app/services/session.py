"""Session 与 Run 业务逻辑层。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.agent import AgentConfig
from app.models.session import SessionRecord
from app.models.token_usage import TokenUsageLog
from app.schemas.session import MessageItem, RunRequest, RunResponse, SessionCreate, TokenUsageResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


async def create_session(db: AsyncSession, data: SessionCreate) -> SessionRecord:
    """创建 Session，校验 Agent 存在性。"""
    # 校验 Agent 存在
    stmt = select(AgentConfig).where(AgentConfig.name == data.agent_name, AgentConfig.is_active == True)  # noqa: E712
    agent_config = (await db.execute(stmt)).scalar_one_or_none()
    if agent_config is None:
        raise NotFoundError(f"Agent '{data.agent_name}' 不存在")

    session = SessionRecord(
        agent_name=data.agent_name,
        metadata_=data.metadata,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> SessionRecord:
    """获取 Session 详情。"""
    stmt = select(SessionRecord).where(SessionRecord.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError(f"Session '{session_id}' 不存在")
    return session


async def list_sessions(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[SessionRecord], int]:
    """获取 Session 列表（分页）。"""
    base = select(SessionRecord)
    if agent_name:
        base = base.where(SessionRecord.agent_name == agent_name)
    if status:
        base = base.where(SessionRecord.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(SessionRecord.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """删除 Session。"""
    session = await get_session(db, session_id)
    await db.delete(session)
    await db.commit()


# ---------------------------------------------------------------------------
# Agent 构建辅助
# ---------------------------------------------------------------------------


def _build_agent_from_config(config: AgentConfig) -> Any:
    """从 DB AgentConfig 构造 Framework Agent 实例。"""
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.model.settings import ModelSettings

    model_settings = None
    if config.model_settings:
        model_settings = ModelSettings(**config.model_settings)

    return Agent(
        name=config.name,
        description=config.description,
        instructions=config.instructions,
        model=config.model,
        model_settings=model_settings,
        # tools/handoffs 由 tool_groups/handoffs 名称解析（MVP 暂不实现工具注册）
    )


# ---------------------------------------------------------------------------
# Token Usage 采集辅助
# ---------------------------------------------------------------------------


async def _save_token_usage_from_trace(
    db: AsyncSession,
    trace: Any,
    *,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    """从 RunResult.trace 中提取 LLM Span 的 token_usage，写入 token_usage_logs。"""
    if trace is None or not hasattr(trace, "spans"):
        return

    logs: list[TokenUsageLog] = []
    for span in trace.spans:
        # 只采集 LLM 类型且有 token_usage 的 Span
        if getattr(span, "type", None) != "llm":
            continue
        usage = getattr(span, "token_usage", None)
        if not usage:
            continue

        # 查找父 agent span 获取 agent_name
        agent_name = _find_parent_agent_name(trace.spans, span) or "unknown"

        logs.append(
            TokenUsageLog(
                trace_id=trace.trace_id,
                span_id=span.span_id,
                session_id=session_id,
                user_id=user_id,
                agent_name=agent_name,
                model=span.model or span.name or "unknown",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        )

    if logs:
        try:
            db.add_all(logs)
            await db.commit()
        except Exception:
            logger.exception("Failed to save token usage logs")
            await db.rollback()


def _find_parent_agent_name(spans: list[Any], target_span: Any) -> str | None:
    """在 spans 列表中查找 target_span 的父 Agent Span 名称。"""
    if target_span.parent_span_id is None:
        return None
    for span in spans:
        if span.span_id == target_span.parent_span_id and getattr(span, "type", None) == "agent":
            return span.name
    return None


# ---------------------------------------------------------------------------
# Run 执行
# ---------------------------------------------------------------------------


async def execute_run(
    db: AsyncSession,
    session_id: uuid.UUID,
    request: RunRequest,
) -> RunResponse:
    """非流式执行 Run：加载 Agent 配置 → Runner.run。"""
    from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
    from ckyclaw_framework.runner.run_config import RunConfig as FrameworkRunConfig
    from ckyclaw_framework.runner.runner import Runner
    from ckyclaw_framework.session.in_memory import InMemorySessionBackend
    from ckyclaw_framework.session.session import Session

    # 获取 session 记录
    session_record = await get_session(db, session_id)

    # 获取 Agent 配置
    stmt = select(AgentConfig).where(
        AgentConfig.name == session_record.agent_name,
        AgentConfig.is_active == True,  # noqa: E712
    )
    agent_config = (await db.execute(stmt)).scalar_one_or_none()
    if agent_config is None:
        raise NotFoundError(f"Agent '{session_record.agent_name}' 不存在或已被禁用")

    # 构建 Framework Agent
    agent = _build_agent_from_config(agent_config)

    # 构建 Framework Session（使用 InMemory，消息随请求生命周期）
    # TODO: 后续切换到 PostgresSessionBackend 实现跨请求持久化
    session_backend = InMemorySessionBackend()
    framework_session = Session(session_id=str(session_id), backend=session_backend)

    # 构建 RunConfig
    model = request.config.model_override or agent_config.model
    framework_config = FrameworkRunConfig(
        model=model,
        model_provider=LiteLLMProvider(),
    )

    # 执行
    run_id = str(uuid.uuid4())
    start_time = time.monotonic()

    result = await Runner.run(
        agent=agent,
        input=request.input,
        session=framework_session,
        config=framework_config,
        max_turns=request.config.max_turns,
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # Token 审计：从 Trace 提取 LLM Span token_usage 写入
    await _save_token_usage_from_trace(db, result.trace, session_id=session_id)

    # 更新 session 的 updated_at
    session_record.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 构建响应
    token_usage = TokenUsageResponse()
    if result.token_usage:
        token_usage = TokenUsageResponse(
            prompt_tokens=result.token_usage.prompt_tokens,
            completion_tokens=result.token_usage.completion_tokens,
            total_tokens=result.token_usage.total_tokens,
        )

    return RunResponse(
        run_id=run_id,
        status="completed",
        output=result.output,
        token_usage=token_usage,
        duration_ms=duration_ms,
        turn_count=result.turn_count,
        last_agent_name=result.last_agent_name,
    )


async def execute_run_stream(
    db: AsyncSession,
    session_id: uuid.UUID,
    request: RunRequest,
) -> AsyncIterator[str]:
    """流式执行 Run：返回 SSE 事件字符串生成器。"""
    from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
    from ckyclaw_framework.runner.result import StreamEventType
    from ckyclaw_framework.runner.run_config import RunConfig as FrameworkRunConfig
    from ckyclaw_framework.runner.runner import Runner
    from ckyclaw_framework.session.in_memory import InMemorySessionBackend
    from ckyclaw_framework.session.session import Session

    # 获取 session 记录
    session_record = await get_session(db, session_id)

    # 获取 Agent 配置
    stmt = select(AgentConfig).where(
        AgentConfig.name == session_record.agent_name,
        AgentConfig.is_active == True,  # noqa: E712
    )
    agent_config = (await db.execute(stmt)).scalar_one_or_none()
    if agent_config is None:
        raise NotFoundError(f"Agent '{session_record.agent_name}' 不存在或已被禁用")

    agent = _build_agent_from_config(agent_config)

    session_backend = InMemorySessionBackend()
    framework_session = Session(session_id=str(session_id), backend=session_backend)

    model = request.config.model_override or agent_config.model
    framework_config = FrameworkRunConfig(
        model=model,
        model_provider=LiteLLMProvider(),
    )

    run_id = str(uuid.uuid4())
    start_time = time.monotonic()
    run_result = None  # 用于提取 trace → token_usage_logs

    # SSE 事件映射
    _EVENT_MAP = {
        StreamEventType.AGENT_START: "agent_start",
        StreamEventType.AGENT_END: "agent_end",
        StreamEventType.LLM_CHUNK: "text_delta",
        StreamEventType.TOOL_CALL_START: "tool_call_start",
        StreamEventType.TOOL_CALL_END: "tool_call_end",
        StreamEventType.HANDOFF: "handoff",
        StreamEventType.RUN_COMPLETE: "run_end",
    }

    # 发送 run_start
    yield _sse_event("run_start", {"run_id": run_id, "agent_name": agent.name})

    try:
        async for event in Runner.run_streamed(
            agent=agent,
            input=request.input,
            session=framework_session,
            config=framework_config,
            max_turns=request.config.max_turns,
        ):
            event_name = _EVENT_MAP.get(event.type, event.type.value)
            payload: dict[str, Any] = {"agent_name": event.agent_name}

            if event.type == StreamEventType.LLM_CHUNK:
                payload["delta"] = event.data if isinstance(event.data, str) else str(event.data or "")
            elif event.type == StreamEventType.RUN_COMPLETE:
                run_result = event.data  # RunResult
                duration_ms = int((time.monotonic() - start_time) * 1000)
                payload["run_id"] = run_id
                payload["status"] = "completed"
                payload["duration_ms"] = duration_ms
                if event.data and hasattr(event.data, "total_tokens"):
                    payload["total_tokens"] = event.data.total_tokens
            elif event.data is not None:
                if isinstance(event.data, dict):
                    payload.update(event.data)
                elif isinstance(event.data, str):
                    payload["data"] = event.data
                else:
                    payload["data"] = str(event.data)

            yield _sse_event(event_name, payload)

    except Exception as exc:
        logger.exception("Run 执行异常: session_id=%s", session_id)
        yield _sse_event("error", {"code": "RUN_FAILED", "message": str(exc)})

    # Token 审计：从 Trace 提取 LLM Span token_usage 写入
    if run_result and hasattr(run_result, "trace"):
        await _save_token_usage_from_trace(db, run_result.trace, session_id=session_id)

    # 更新 session
    session_record.updated_at = datetime.now(timezone.utc)
    await db.commit()


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """格式化 SSE 事件字符串。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
