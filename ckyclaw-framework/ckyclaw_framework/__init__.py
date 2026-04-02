"""CkyClaw Framework — Python Agent 运行时框架"""

from __future__ import annotations

# === Core ===
from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.result import RunResult, StreamEvent

# === Orchestration ===
from ckyclaw_framework.handoff.handoff import Handoff, InputFilter

# === Tools ===
from ckyclaw_framework.tools.function_tool import FunctionTool, function_tool
from ckyclaw_framework.tools.tool_context import ToolContext

# === Session ===
from ckyclaw_framework.session.session import Session, SessionBackend, SessionMetadata
from ckyclaw_framework.session.in_memory import InMemorySessionBackend

# === Tracing ===
from ckyclaw_framework.tracing.trace import Trace
from ckyclaw_framework.tracing.span import Span, SpanType, SpanStatus
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.console_processor import ConsoleTraceProcessor

# === Model ===
from ckyclaw_framework.model.provider import ModelProvider, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider

__all__ = [
    # Core
    "Agent",
    "Runner",
    "RunConfig",
    "RunContext",
    "RunResult",
    "StreamEvent",
    # Orchestration
    "Handoff",
    "InputFilter",
    # Tools
    "FunctionTool",
    "function_tool",
    "ToolContext",
    # Session
    "Session",
    "SessionBackend",
    "SessionMetadata",
    "InMemorySessionBackend",
    # Tracing
    "Trace",
    "Span",
    "SpanType",
    "SpanStatus",
    "TraceProcessor",
    "ConsoleTraceProcessor",
    # Model
    "ModelProvider",
    "ModelSettings",
    "Message",
    "MessageRole",
    "TokenUsage",
    "ToolCall",
    "ToolCallChunk",
    "LiteLLMProvider",
]

__version__ = "0.1.0"
