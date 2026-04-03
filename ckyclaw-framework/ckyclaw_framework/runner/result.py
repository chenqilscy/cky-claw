"""RunResult / StreamEvent — 执行结果与流式事件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message, TokenUsage
    from ckyclaw_framework.tracing.trace import Trace


@dataclass
class RunResult:
    """Agent 执行结果。"""

    output: Any
    """Agent 最终输出（字符串或结构化对象，取决于 Agent.output_type）"""

    messages: list[Message] = field(default_factory=list)
    """完整消息历史"""

    last_agent_name: str | None = None
    """最终处理消息的 Agent 名称"""

    token_usage: TokenUsage | None = None
    """累计 Token 消耗"""

    trace: Trace | None = None
    """完整链路追踪"""

    turn_count: int = 0
    """实际执行轮次"""


class StreamEventType(str, Enum):
    """流式事件类型。"""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    LLM_CHUNK = "llm_chunk"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    HANDOFF = "handoff"
    RUN_COMPLETE = "run_complete"


@dataclass
class StreamEvent:
    """流式输出事件。"""

    type: StreamEventType
    data: Any = None
    agent_name: str | None = None
