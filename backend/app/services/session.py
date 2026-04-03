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


_MAX_HANDOFF_DEPTH = 5
"""Handoff 递归构建最大深度，防止循环引用或无限递归。"""


async def _resolve_mcp_tools(
    db: AsyncSession,
    config: AgentConfig,
    stack: Any | None = None,
) -> list[Any]:
    """从 AgentConfig.mcp_servers 名称列表加载 MCP Server 配置并连接。

    当提供 ``stack`` (AsyncExitStack) 时，实际连接 MCP Server 并发现工具。
    未提供时仅做配置日志记录。
    """
    if not config.mcp_servers:
        return []

    from app.services.mcp_server import get_mcp_servers_by_names

    mcp_configs = await get_mcp_servers_by_names(db, config.mcp_servers)

    # 检查缺失的 MCP Server
    found_names = {c.name for c in mcp_configs}
    for name in config.mcp_servers:
        if name not in found_names:
            logger.warning("MCP Server '%s' 不存在或已禁用，Agent '%s' 无法加载其工具", name, config.name)

    if not mcp_configs:
        return []

    # 无 stack 时仅日志，不实际连接
    if stack is None:
        server_names = [c.name for c in mcp_configs]
        logger.info(
            "Agent '%s' 关联 %d 个 MCP Server: %s（未提供 AsyncExitStack，跳过连接）",
            config.name,
            len(mcp_configs),
            server_names,
        )
        return []

    # 实际连接 MCP Server，发现工具
    from app.core.crypto import decrypt_api_key
    from ckyclaw_framework.mcp.connection import connect_and_discover
    from ckyclaw_framework.mcp.server import MCPServerConfig as FrameworkMCPConfig

    all_tools: list[Any] = []
    for db_config in mcp_configs:
        # 解密 auth_config 中的敏感字段作为 headers
        headers: dict[str, str] = {}
        if db_config.auth_config:
            for key, value in db_config.auth_config.items():
                if isinstance(value, str) and value:
                    try:
                        headers[key] = decrypt_api_key(value)
                    except Exception:
                        headers[key] = value

        # 解密 env 中的值（如果是加密的）
        env: dict[str, str] = {}
        if db_config.env:
            for key, value in db_config.env.items():
                env[key] = str(value) if value else ""

        fw_config = FrameworkMCPConfig(
            name=db_config.name,
            transport=db_config.transport_type,
            command=db_config.command,
            url=db_config.url,
            env=env,
            headers=headers,
        )

        try:
            tools = await connect_and_discover(stack, fw_config)
            all_tools.extend(tools)
        except ImportError:
            logger.warning("MCP SDK 未安装，跳过 MCP Server '%s'", db_config.name)
            break
        except Exception:
            logger.exception("MCP Server '%s' 连接异常", db_config.name)

    logger.info(
        "Agent '%s' 通过 %d 个 MCP Server 加载了 %d 个工具",
        config.name,
        len(mcp_configs),
        len(all_tools),
    )
    return all_tools


async def _resolve_tool_groups(
    db: AsyncSession,
    config: AgentConfig,
) -> list[Any]:
    """从 AgentConfig.tool_groups 名称列表加载工具组配置，返回 FunctionTool 列表。

    每个工具组包含若干工具定义（name/description/parameters_schema），
    每个定义被包装为一个 FunctionTool（fn=None，执行时返回未实现提示）。
    """
    if not config.tool_groups:
        return []

    from app.models.tool_group import ToolGroupConfig
    from ckyclaw_framework.tools.function_tool import FunctionTool

    stmt = select(ToolGroupConfig).where(
        ToolGroupConfig.name.in_(config.tool_groups),
        ToolGroupConfig.is_enabled == True,  # noqa: E712
    )
    tg_configs = {c.name: c for c in (await db.execute(stmt)).scalars().all()}

    # 检查缺失的工具组
    for name in config.tool_groups:
        if name not in tg_configs:
            logger.warning("工具组 '%s' 不存在或已禁用，Agent '%s' 无法加载其工具", name, config.name)

    tools: list[Any] = []
    for name in config.tool_groups:
        tg = tg_configs.get(name)
        if tg is None:
            continue
        for tool_def in tg.tools or []:
            if not isinstance(tool_def, dict):
                continue
            tool_name = tool_def.get("name")
            if not tool_name:
                continue
            ft = FunctionTool(
                name=tool_name,
                description=tool_def.get("description", ""),
                parameters_schema=tool_def.get("parameters_schema", {"type": "object", "properties": {}}),
                group=name,
            )
            tools.append(ft)

    logger.info(
        "Agent '%s' 从 %d 个工具组加载了 %d 个工具",
        config.name,
        len(tg_configs),
        len(tools),
    )
    return tools


# JSON Schema type 到 Python annotation 的映射
_JSON_SCHEMA_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _build_output_type_from_schema(schema: dict[str, Any], agent_name: str) -> type | None:
    """从 JSON Schema 动态构建 Pydantic BaseModel 类。

    仅支持 flat 对象结构（properties 均为基本类型或 array[string]）。
    复杂嵌套场景在后续迭代中扩展。
    """
    from pydantic import create_model

    properties = schema.get("properties")
    if not properties:
        return None

    required_set = set(schema.get("required", []))
    field_definitions: dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        if field_type == "array":
            items_type = field_schema.get("items", {}).get("type", "string")
            python_type = list[_JSON_SCHEMA_TYPE_MAP.get(items_type, str)]  # type: ignore[index]
        else:
            python_type = _JSON_SCHEMA_TYPE_MAP.get(field_type, str)  # type: ignore[assignment]

        if field_name in required_set:
            field_definitions[field_name] = (python_type, ...)
        else:
            default = field_schema.get("default")
            field_definitions[field_name] = (python_type, default)

    # 使用 Agent name 生成可辨识的 Model 类名
    model_name = f"{agent_name.replace('-', '_').title().replace('_', '')}Output"
    return create_model(model_name, **field_definitions)


def _build_agent_from_config(
    config: AgentConfig,
    guardrail_rules: list | None = None,
    handoff_agents: list[Any] | None = None,
    mcp_tools: list[Any] | None = None,
) -> Any:
    """从 DB AgentConfig 构造 Framework Agent 实例。"""
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.approval.mode import ApprovalMode
    from ckyclaw_framework.guardrails.content_safety_guardrail import ContentSafetyGuardrail
    from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
    from ckyclaw_framework.guardrails.llm_guardrail import LLMGuardrail
    from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
    from ckyclaw_framework.guardrails.prompt_injection_guardrail import PromptInjectionGuardrail
    from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail
    from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
    from ckyclaw_framework.model.settings import ModelSettings

    model_settings = None
    if config.model_settings:
        model_settings = ModelSettings(**config.model_settings)

    # 构建 Input Guardrails
    input_guardrails: list[InputGuardrail] = []
    # 构建 Output Guardrails
    output_guardrails: list[OutputGuardrail] = []
    # 构建 Tool Guardrails
    tool_guardrails: list[ToolGuardrail] = []
    if guardrail_rules:
        for rule in guardrail_rules:
            rule_config = rule.config or {}
            if rule.mode == "regex":
                rg = RegexGuardrail(
                    patterns=rule_config.get("patterns", []),
                    message=rule_config.get("message", f"规则 '{rule.name}' 拦截"),
                    name=rule.name,
                )
            elif rule.mode == "keyword":
                rg = RegexGuardrail(
                    keywords=rule_config.get("keywords", []),
                    message=rule_config.get("message", f"规则 '{rule.name}' 拦截"),
                    name=rule.name,
                )
            elif rule.mode == "llm":
                preset = rule_config.get("preset", "custom")
                if preset == "prompt_injection":
                    lg: LLMGuardrail = PromptInjectionGuardrail(
                        name=rule.name,
                        model=rule_config.get("model", "gpt-4o-mini"),
                        threshold=rule_config.get("threshold", 0.7),
                    )
                elif preset == "content_safety":
                    lg = ContentSafetyGuardrail(
                        name=rule.name,
                        model=rule_config.get("model", "gpt-4o-mini"),
                        threshold=rule_config.get("threshold", 0.75),
                    )
                else:  # custom
                    lg = LLMGuardrail(
                        name=rule.name,
                        model=rule_config.get("model", "gpt-4o-mini"),
                        prompt_template=rule_config.get("prompt_template", ""),
                        threshold=rule_config.get("threshold", 0.8),
                    )

                if rule.type == "input":
                    input_guardrails.append(InputGuardrail(
                        guardrail_function=lg.as_input_fn(),
                        name=rule.name,
                    ))
                elif rule.type == "output":
                    output_guardrails.append(OutputGuardrail(
                        guardrail_function=lg.as_output_fn(),
                        name=rule.name,
                    ))
                elif rule.type == "tool":
                    tool_guardrails.append(ToolGuardrail(
                        name=rule.name,
                        before_fn=lg.as_tool_before_fn(),
                        after_fn=lg.as_tool_after_fn(),
                    ))
                continue
            else:
                continue

            if rule.type == "input":
                input_guardrails.append(InputGuardrail(
                    guardrail_function=rg.as_input_fn(),
                    name=rule.name,
                ))
            elif rule.type == "output":
                output_guardrails.append(OutputGuardrail(
                    guardrail_function=rg.as_output_fn(),
                    name=rule.name,
                ))
            elif rule.type == "tool":
                tool_guardrails.append(ToolGuardrail(
                    name=rule.name,
                    before_fn=rg.as_tool_before_fn(),
                    after_fn=rg.as_tool_after_fn(),
                ))

    # 解析 approval_mode
    approval_mode_map = {
        "suggest": ApprovalMode.SUGGEST,
        "auto-edit": ApprovalMode.AUTO_EDIT,
        "full-auto": ApprovalMode.FULL_AUTO,
    }
    approval_mode = approval_mode_map.get(config.approval_mode)

    # 解析 output_type: JSON Schema → 动态 Pydantic Model
    output_type = None
    if config.output_type:
        output_type = _build_output_type_from_schema(config.output_type, config.name)

    return Agent(
        name=config.name,
        description=config.description,
        instructions=config.instructions,
        model=config.model,
        model_settings=model_settings,
        tools=mcp_tools or [],
        input_guardrails=input_guardrails,
        output_guardrails=output_guardrails,
        tool_guardrails=tool_guardrails,
        approval_mode=approval_mode,
        handoffs=handoff_agents or [],
        output_type=output_type,
    )


async def _resolve_handoff_agents(
    db: AsyncSession,
    config: AgentConfig,
    visited: set[str] | None = None,
    depth: int = 0,
) -> list[Any]:
    """递归解析 AgentConfig.handoffs 名称列表，构建 Framework Agent 对象图。

    - 使用 visited 集合检测循环引用
    - 使用 depth 限制递归深度
    - 缺失或禁用的目标 Agent 被安全跳过（warn）
    """
    from ckyclaw_framework.handoff.handoff import Handoff

    if not config.handoffs:
        return []

    if depth >= _MAX_HANDOFF_DEPTH:
        logger.warning(
            "Handoff 递归深度达到上限 %d，Agent '%s' 的 handoffs 将被截断",
            _MAX_HANDOFF_DEPTH,
            config.name,
        )
        return []

    if visited is None:
        visited = set()
    visited = visited | {config.name}  # 不可变拷贝，每条路径独立

    # 批量加载目标 AgentConfig
    target_names = [n for n in config.handoffs if n not in visited]
    if not target_names:
        # 所有 handoff 目标都在 visited 中（循环引用）
        for name in config.handoffs:
            if name in visited:
                logger.warning("检测到循环 Handoff 引用：Agent '%s' → '%s'，已跳过", config.name, name)
        return []

    stmt = select(AgentConfig).where(
        AgentConfig.name.in_(target_names),
        AgentConfig.is_active == True,  # noqa: E712
    )
    target_configs = {c.name: c for c in (await db.execute(stmt)).scalars().all()}

    # 加载目标 Agent 的 Guardrail 规则
    from app.services.guardrail import get_guardrail_rules_by_names

    handoff_list: list[Any] = []
    for name in config.handoffs:
        if name in visited and name not in target_names:
            logger.warning("检测到循环 Handoff 引用：Agent '%s' → '%s'，已跳过", config.name, name)
            continue

        target_config = target_configs.get(name)
        if target_config is None:
            logger.warning("Handoff 目标 Agent '%s' 不存在或已禁用，已跳过", name)
            continue

        # 加载目标的 guardrail 规则（input + output + tool）
        _tgr = target_config.guardrails or {}
        target_guardrail_names = list(set(_tgr.get("input", []) + _tgr.get("output", []) + _tgr.get("tool", [])))
        target_guardrail_rules = await get_guardrail_rules_by_names(db, target_guardrail_names)

        # 递归解析目标的 handoffs
        sub_handoffs = await _resolve_handoff_agents(db, target_config, visited, depth + 1)

        # 构建目标 Agent
        target_agent = _build_agent_from_config(
            target_config,
            guardrail_rules=target_guardrail_rules,
            handoff_agents=sub_handoffs,
        )

        handoff_list.append(Handoff(agent=target_agent))

    return handoff_list


_MAX_AGENT_TOOL_DEPTH = 3
"""Agent-as-Tool 递归构建最大深度，防止循环引用或无限递归。"""


async def _resolve_agent_tools(
    db: AsyncSession,
    config: AgentConfig,
    run_config: Any | None = None,
    visited: set[str] | None = None,
    depth: int = 0,
) -> list[Any]:
    """解析 AgentConfig.agent_tools 名称列表，将每个 Agent 包装为 FunctionTool。

    - 使用 visited 集合检测循环引用
    - 使用 depth 限制递归深度
    - 缺失或禁用的目标 Agent 被安全跳过（warn）
    """
    if not config.agent_tools:
        return []

    if depth >= _MAX_AGENT_TOOL_DEPTH:
        logger.warning(
            "Agent-as-Tool 递归深度达到上限 %d，Agent '%s' 的 agent_tools 将被截断",
            _MAX_AGENT_TOOL_DEPTH,
            config.name,
        )
        return []

    if visited is None:
        visited = set()
    visited = visited | {config.name}

    # 批量加载目标 AgentConfig
    target_names = [n for n in config.agent_tools if n not in visited]
    if not target_names:
        for name in config.agent_tools:
            if name in visited:
                logger.warning("检测到循环 Agent-as-Tool 引用：Agent '%s' → '%s'，已跳过", config.name, name)
        return []

    stmt = select(AgentConfig).where(
        AgentConfig.name.in_(target_names),
        AgentConfig.is_active == True,  # noqa: E712
    )
    target_configs = {c.name: c for c in (await db.execute(stmt)).scalars().all()}

    from app.services.guardrail import get_guardrail_rules_by_names

    tool_list: list[Any] = []
    for name in config.agent_tools:
        if name in visited and name not in target_names:
            logger.warning("检测到循环 Agent-as-Tool 引用：Agent '%s' → '%s'，已跳过", config.name, name)
            continue

        target_config = target_configs.get(name)
        if target_config is None:
            logger.warning("Agent-as-Tool 目标 Agent '%s' 不存在或已禁用，已跳过", name)
            continue

        # 加载目标的 guardrail 规则（input + output + tool）
        _tgr = target_config.guardrails or {}
        target_guardrail_names = list(set(_tgr.get("input", []) + _tgr.get("output", []) + _tgr.get("tool", [])))
        target_guardrail_rules = await get_guardrail_rules_by_names(db, target_guardrail_names)

        # 递归解析目标的 handoffs 和 agent_tools
        sub_handoffs = await _resolve_handoff_agents(db, target_config, visited, depth + 1)
        sub_agent_tools = await _resolve_agent_tools(db, target_config, run_config, visited, depth + 1)

        # 构建目标 Agent
        target_agent = _build_agent_from_config(
            target_config,
            guardrail_rules=target_guardrail_rules,
            handoff_agents=sub_handoffs,
            mcp_tools=sub_agent_tools,  # 子 Agent 自身的 agent_tools 作为其工具
        )

        # 将 Agent 包装为 FunctionTool
        tool = target_agent.as_tool(config=run_config)
        tool_list.append(tool)

    return tool_list


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


async def _save_trace_from_processor(
    db: AsyncSession,
    processor: Any,
) -> None:
    """从 PostgresTraceProcessor 收集的数据写入 traces/spans 表。"""
    from app.models.trace import SpanRecord, TraceRecord

    trace_data, span_data_list = processor.get_collected_data()
    if trace_data is None:
        return

    try:
        trace_record = TraceRecord(**trace_data)
        span_records = [SpanRecord(**sd) for sd in span_data_list]
        db.add(trace_record)
        if span_records:
            db.add_all(span_records)
        await db.flush()
    except Exception:
        logger.exception("Failed to save trace data")
        await db.rollback()


# ---------------------------------------------------------------------------
# 会话消息查询
# ---------------------------------------------------------------------------


async def get_session_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list:
    """获取会话的持久化消息列表。"""
    from app.models.session_message import SessionMessage

    # 确保 session 存在
    await get_session(db, session_id)

    stmt = (
        select(SessionMessage)
        .where(SessionMessage.session_id == str(session_id))
        .order_by(SessionMessage.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Provider 解析辅助
# ---------------------------------------------------------------------------


async def _resolve_provider(
    db: AsyncSession,
    agent_config: AgentConfig,
) -> dict[str, str | None]:
    """从 AgentConfig.provider_name 加载 ProviderConfig，返回 LiteLLMProvider 构造参数。

    Returns:
        dict with keys: api_key, api_base, extra_headers (all optional).
        若 provider_name 为空或 Provider 未找到/已禁用，返回空 dict（使用环境变量）。
    """
    provider_name = getattr(agent_config, "provider_name", None)
    if not provider_name:
        return {}

    from app.core.crypto import decrypt_api_key
    from app.models.provider import ProviderConfig

    stmt = select(ProviderConfig).where(
        ProviderConfig.name == provider_name,
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if provider is None:
        logger.warning("Agent '%s' 指定的 Provider '%s' 不存在", agent_config.name, provider_name)
        return {}

    if not provider.is_enabled:
        raise NotFoundError(f"Provider '{provider_name}' 已被禁用，无法执行 Agent '{agent_config.name}'")

    result: dict[str, str | None] = {}

    # 解密 API Key
    if provider.api_key_encrypted:
        try:
            result["api_key"] = decrypt_api_key(provider.api_key_encrypted)
        except Exception:
            logger.exception("Provider '%s' API Key 解密失败", provider_name)
            raise NotFoundError(f"Provider '{provider_name}' API Key 解密失败，请重新配置")

    # Base URL
    if provider.base_url:
        result["api_base"] = provider.base_url

    # 额外认证头（auth_config 中的 KV 对）
    if provider.auth_config:
        headers: dict[str, str] = {}
        for key, value in provider.auth_config.items():
            if isinstance(value, str) and value:
                try:
                    headers[key] = decrypt_api_key(value)
                except Exception:
                    headers[key] = value
        if headers:
            result["extra_headers"] = headers  # type: ignore[assignment]

    logger.info(
        "Agent '%s' 使用 Provider '%s' (type=%s, base_url=%s)",
        agent_config.name,
        provider_name,
        provider.provider_type,
        provider.base_url,
    )
    return result


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

    # 加载 Guardrail 规则（input + output + tool）
    from app.services.guardrail import get_guardrail_rules_by_names

    _gr_cfg = agent_config.guardrails or {}
    guardrail_names = list(set(_gr_cfg.get("input", []) + _gr_cfg.get("output", []) + _gr_cfg.get("tool", [])))
    guardrail_rules = await get_guardrail_rules_by_names(db, guardrail_names)

    # 解析 Handoff 目标 Agent 图
    handoff_agents = await _resolve_handoff_agents(db, agent_config)

    # 解析 Provider 配置
    provider_kwargs = await _resolve_provider(db, agent_config)

    # 加载 MCP Server 工具（通过 AsyncExitStack 管理连接生命周期）
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as mcp_stack:
        mcp_tools = await _resolve_mcp_tools(db, agent_config, stack=mcp_stack)

        # 解析 Agent-as-Tool（子 Agent 包装为 FunctionTool）
        # 先创建子 Agent 的轻量 RunConfig（共享 model_provider，无 trace/approval）
        sub_model_provider = LiteLLMProvider(**provider_kwargs)
        sub_run_config = FrameworkRunConfig(
            model=request.config.model_override or agent_config.model,
            model_provider=sub_model_provider,
        )
        agent_tool_fns = await _resolve_agent_tools(db, agent_config, run_config=sub_run_config)

        # 加载工具组中的工具
        tg_tools = await _resolve_tool_groups(db, agent_config)

        # 合并所有工具
        all_tools = mcp_tools + agent_tool_fns + tg_tools

        # 构建 Framework Agent
        agent = _build_agent_from_config(
            agent_config, guardrail_rules=guardrail_rules, handoff_agents=handoff_agents, mcp_tools=all_tools,
        )

        # 构建 Framework Session（持久化到 PostgreSQL）
        from app.services.session_backend import SQLAlchemySessionBackend

        session_backend = SQLAlchemySessionBackend(db)
        framework_session = Session(session_id=str(session_id), backend=session_backend)

        # 构建 RunConfig（含 Trace 持久化 Processor + Approval Handler）
        from app.services.approval_handler import HttpApprovalHandler
        from app.services.trace_processor import PostgresTraceProcessor

        run_id = str(uuid.uuid4())
        trace_processor = PostgresTraceProcessor(session_id=str(session_id))
        model = request.config.model_override or agent_config.model

        # 审批处理器：非 full-auto 模式时创建 HttpApprovalHandler
        approval_handler = None
        if agent_config.approval_mode and agent_config.approval_mode != "full-auto":
            approval_handler = HttpApprovalHandler(
                session_id=str(session_id),
                run_id=run_id,
                agent_name=agent_config.name,
            )

        framework_config = FrameworkRunConfig(
            model=model,
            model_provider=LiteLLMProvider(**provider_kwargs),
            trace_processors=[trace_processor],
            approval_handler=approval_handler,
        )

        # 执行
        start_time = time.monotonic()

        from ckyclaw_framework.guardrails.result import (
            InputGuardrailTripwireError,
            OutputGuardrailTripwireError,
        )

        try:
            result = await Runner.run(
                agent=agent,
                input=request.input,
                session=framework_session,
                config=framework_config,
                max_turns=request.config.max_turns,
            )
        except InputGuardrailTripwireError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return RunResponse(
                run_id=run_id,
                status="guardrail_blocked",
                output=f"[Input Guardrail] {exc.guardrail_name}: {exc.message}",
                token_usage=TokenUsageResponse(),
                duration_ms=duration_ms,
                turn_count=0,
                last_agent_name=agent_config.name,
            )
        except OutputGuardrailTripwireError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return RunResponse(
                run_id=run_id,
                status="guardrail_blocked",
                output=f"[Output Guardrail] {exc.guardrail_name}: {exc.message}",
                token_usage=TokenUsageResponse(),
                duration_ms=duration_ms,
                turn_count=0,
                last_agent_name=agent_config.name,
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)

    # ---- MCP 连接已关闭，以下为后处理 ----

    # Token 审计：从 Trace 提取 LLM Span token_usage 写入
    await _save_token_usage_from_trace(db, result.trace, session_id=session_id)

    # Trace 持久化：写入 traces/spans 表
    await _save_trace_from_processor(db, trace_processor)

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

    # 加载 Guardrail 规则（input + output + tool）
    from app.services.guardrail import get_guardrail_rules_by_names

    _gr_cfg = agent_config.guardrails or {}
    guardrail_names = list(set(_gr_cfg.get("input", []) + _gr_cfg.get("output", []) + _gr_cfg.get("tool", [])))
    guardrail_rules = await get_guardrail_rules_by_names(db, guardrail_names)

    # 解析 Handoff 目标 Agent 图
    handoff_agents = await _resolve_handoff_agents(db, agent_config)

    # 解析 Provider 配置
    provider_kwargs = await _resolve_provider(db, agent_config)

    # 加载 MCP Server 工具（通过 AsyncExitStack 管理连接生命周期）
    from contextlib import AsyncExitStack

    mcp_stack = AsyncExitStack()
    await mcp_stack.__aenter__()
    try:
        mcp_tools = await _resolve_mcp_tools(db, agent_config, stack=mcp_stack)
    except Exception:
        await mcp_stack.__aexit__(None, None, None)
        raise

    # 解析 Agent-as-Tool
    sub_model_provider = LiteLLMProvider(**provider_kwargs)
    sub_run_config = FrameworkRunConfig(
        model=request.config.model_override or agent_config.model,
        model_provider=sub_model_provider,
    )
    try:
        agent_tool_fns = await _resolve_agent_tools(db, agent_config, run_config=sub_run_config)
    except Exception:
        await mcp_stack.__aexit__(None, None, None)
        raise

    # 加载工具组中的工具
    try:
        tg_tools = await _resolve_tool_groups(db, agent_config)
    except Exception:
        await mcp_stack.__aexit__(None, None, None)
        raise

    all_tools = mcp_tools + agent_tool_fns + tg_tools

    agent = _build_agent_from_config(
        agent_config, guardrail_rules=guardrail_rules, handoff_agents=handoff_agents, mcp_tools=all_tools,
    )

    from app.services.session_backend import SQLAlchemySessionBackend

    session_backend = SQLAlchemySessionBackend(db)
    framework_session = Session(session_id=str(session_id), backend=session_backend)

    # 构建 RunConfig（含 Trace 持久化 Processor + Approval Handler）
    from app.services.approval_handler import HttpApprovalHandler
    from app.services.trace_processor import PostgresTraceProcessor

    run_id = str(uuid.uuid4())
    trace_processor = PostgresTraceProcessor(session_id=str(session_id))
    model = request.config.model_override or agent_config.model

    # 审批处理器：非 full-auto 模式时创建 HttpApprovalHandler
    approval_handler = None
    if agent_config.approval_mode and agent_config.approval_mode != "full-auto":
        approval_handler = HttpApprovalHandler(
            session_id=str(session_id),
            run_id=run_id,
            agent_name=agent_config.name,
        )

    framework_config = FrameworkRunConfig(
        model=model,
        model_provider=LiteLLMProvider(**provider_kwargs),
        trace_processors=[trace_processor],
        approval_handler=approval_handler,
    )

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
        from ckyclaw_framework.guardrails.result import (
            InputGuardrailTripwireError,
            OutputGuardrailTripwireError,
        )

        if isinstance(exc, InputGuardrailTripwireError):
            code = "INPUT_GUARDRAIL_TRIGGERED"
            msg = f"[Input Guardrail] {exc.guardrail_name}: {exc.message}"
        elif isinstance(exc, OutputGuardrailTripwireError):
            code = "OUTPUT_GUARDRAIL_TRIGGERED"
            msg = f"[Output Guardrail] {exc.guardrail_name}: {exc.message}"
        else:
            code = "RUN_FAILED"
            msg = str(exc)

        logger.exception("Run 执行异常: session_id=%s, code=%s", session_id, code)
        yield _sse_event("error", {"code": code, "message": msg})
    finally:
        # 关闭 MCP 连接
        await mcp_stack.__aexit__(None, None, None)

    # Token 审计：从 Trace 提取 LLM Span token_usage 写入
    if run_result and hasattr(run_result, "trace"):
        await _save_token_usage_from_trace(db, run_result.trace, session_id=session_id)

    # Trace 持久化：写入 traces/spans 表
    await _save_trace_from_processor(db, trace_processor)

    # 更新 session
    session_record.updated_at = datetime.now(timezone.utc)
    await db.commit()


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """格式化 SSE 事件字符串。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
