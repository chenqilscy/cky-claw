"""EventType — 事件类型枚举。

定义所有可追踪的 Agent 运行事件类型。
粒度比 SpanType 更细，覆盖运行生命周期的每个关键节点。
"""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """事件类型。"""

    # ── Trace 级别 ──
    RUN_START = "run_start"
    RUN_END = "run_end"

    # ── Agent 级别 ──
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"

    # ── LLM 级别 ──
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_END = "llm_call_end"

    # ── 工具级别 ──
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"

    # ── Handoff ──
    HANDOFF = "handoff"

    # ── Guardrail ──
    GUARDRAIL_CHECK_START = "guardrail_check_start"
    GUARDRAIL_CHECK_END = "guardrail_check_end"
    GUARDRAIL_TRIPWIRE = "guardrail_tripwire"

    # ── Approval ──
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"

    # ── Checkpoint ──
    CHECKPOINT_SAVED = "checkpoint_saved"

    # ── Error ──
    ERROR = "error"
