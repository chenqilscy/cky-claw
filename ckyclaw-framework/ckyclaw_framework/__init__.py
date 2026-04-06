"""CkyClaw Framework — Python Agent 运行时框架"""

from __future__ import annotations

# === Core ===
from ckyclaw_framework.agent.agent import Agent, InstructionsType
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.result import RunResult, StreamEvent

# === Orchestration ===
from ckyclaw_framework.handoff.handoff import Handoff, InputFilter

# === Guardrails ===
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
from ckyclaw_framework.guardrails.result import GuardrailResult, InputGuardrailTripwireError, OutputGuardrailTripwireError
from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail
from ckyclaw_framework.guardrails.pii_guardrail import PIIDetectionGuardrail
from ckyclaw_framework.guardrails.max_token_guardrail import MaxTokenGuardrail
from ckyclaw_framework.guardrails.tool_whitelist_guardrail import ToolWhitelistGuardrail
from ckyclaw_framework.guardrails.llm_guardrail import LLMGuardrail
from ckyclaw_framework.guardrails.prompt_injection_guardrail import PromptInjectionGuardrail
from ckyclaw_framework.guardrails.content_safety_guardrail import ContentSafetyGuardrail

# === Approval ===
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError
from ckyclaw_framework.approval.handler import ApprovalHandler

# === Tools ===
from ckyclaw_framework.tools.function_tool import FunctionTool, function_tool
from ckyclaw_framework.tools.tool_context import ToolContext

# === Session ===
from ckyclaw_framework.session.session import Session, SessionBackend, SessionMetadata
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimStrategy, HistoryTrimmer

# === Tracing ===
from ckyclaw_framework.tracing.trace import Trace
from ckyclaw_framework.tracing.span import Span, SpanType, SpanStatus
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.console_processor import ConsoleTraceProcessor

# === Workflow ===
from ckyclaw_framework.workflow.engine import AgentNotFoundError, AgentResolver, WorkflowEngine
from ckyclaw_framework.workflow.workflow import Edge, Workflow
from ckyclaw_framework.workflow.step import (
    AgentStep, BranchCondition, ConditionalStep, LoopStep,
    ParallelStep, RetryConfig, Step, StepIO, StepStatus, StepType,
)
from ckyclaw_framework.workflow.result import StepResult, WorkflowResult, WorkflowStatus
from ckyclaw_framework.workflow.config import WorkflowRunConfig
from ckyclaw_framework.workflow.validator import WorkflowValidationError, topological_sort, validate_workflow, validate_workflow_strict
from ckyclaw_framework.workflow.evaluator import UnsafeExpressionError, evaluate

# === Memory ===
from ckyclaw_framework.memory.memory import DecayMode, MemoryBackend, MemoryEntry, MemoryType, compute_exponential_decay
from ckyclaw_framework.memory.in_memory import InMemoryMemoryBackend
from ckyclaw_framework.memory.retriever import MemoryRetriever
from ckyclaw_framework.memory.hooks import MemoryExtractionHook

# === Skills ===
from ckyclaw_framework.skills.skill import Skill, SkillCategory
from ckyclaw_framework.skills.registry import SkillNotFoundError, SkillRegistry
from ckyclaw_framework.skills.injector import SkillInjector

# === Team ===
from ckyclaw_framework.team.protocol import TeamProtocol
from ckyclaw_framework.team.team import Team, TeamConfig
from ckyclaw_framework.team.team_runner import TeamResult, TeamRunner

# === Sandbox ===
from ckyclaw_framework.sandbox.config import SandboxConfig
from ckyclaw_framework.sandbox.executor import SandboxExecutor, SandboxResult
from ckyclaw_framework.sandbox.local_sandbox import LocalSandbox

# === Checkpoint ===
from ckyclaw_framework.checkpoint import Checkpoint, CheckpointBackend, InMemoryCheckpointBackend

# === Model ===
from ckyclaw_framework.model.provider import ModelProvider, ToolCall, ToolCallChunk
from ckyclaw_framework.model.cost_router import CostRouter, ModelTier, ProviderCandidate, classify_complexity

# === Evolution ===
from ckyclaw_framework.evolution.config import EvolutionConfig
from ckyclaw_framework.evolution.proposal import EvolutionProposal, ProposalStatus, ProposalType
from ckyclaw_framework.evolution.signals import (
    EvolutionSignal,
    FeedbackSignal,
    MetricSignal,
    SignalCollector,
    SignalType,
    ToolPerformanceSignal,
)
from ckyclaw_framework.evolution.strategy import EvolutionStrategy, StrategyEngine
from ckyclaw_framework.model.settings import ModelSettings
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider

__all__ = [
    # Core
    "Agent",
    "InstructionsType",
    "Runner",
    "RunConfig",
    "RunContext",
    "RunResult",
    "StreamEvent",
    # Orchestration
    "Handoff",
    "InputFilter",
    # Guardrails
    "InputGuardrail",
    "OutputGuardrail",
    "ToolGuardrail",
    "GuardrailResult",
    "InputGuardrailTripwireError",
    "OutputGuardrailTripwireError",
    "RegexGuardrail",
    "PIIDetectionGuardrail",
    "MaxTokenGuardrail",
    "ToolWhitelistGuardrail",
    "LLMGuardrail",
    "PromptInjectionGuardrail",
    "ContentSafetyGuardrail",
    # Approval
    "ApprovalDecision",
    "ApprovalMode",
    "ApprovalRejectedError",
    "ApprovalHandler",
    # Tools
    "FunctionTool",
    "function_tool",
    "ToolContext",
    # Session
    "Session",
    "SessionBackend",
    "SessionMetadata",
    "InMemorySessionBackend",
    "HistoryTrimConfig",
    "HistoryTrimStrategy",
    "HistoryTrimmer",
    # Tracing
    "Trace",
    "Span",
    "SpanType",
    "SpanStatus",
    "TraceProcessor",
    "ConsoleTraceProcessor",
    # Workflow
    "WorkflowEngine",
    "AgentNotFoundError",
    "AgentResolver",
    "Workflow",
    "Edge",
    "Step",
    "StepType",
    "StepStatus",
    "StepIO",
    "RetryConfig",
    "AgentStep",
    "ConditionalStep",
    "BranchCondition",
    "ParallelStep",
    "LoopStep",
    "WorkflowResult",
    "WorkflowStatus",
    "StepResult",
    "WorkflowRunConfig",
    "WorkflowValidationError",
    "topological_sort",
    "validate_workflow",
    "validate_workflow_strict",
    "UnsafeExpressionError",
    "evaluate",
    # Memory
    "DecayMode",
    "MemoryType",
    "MemoryEntry",
    "MemoryBackend",
    "InMemoryMemoryBackend",
    "MemoryRetriever",
    "MemoryExtractionHook",
    "compute_exponential_decay",
    # Skills
    "Skill",
    "SkillCategory",
    "SkillRegistry",
    "SkillNotFoundError",
    "SkillInjector",
    # Model
    "ModelProvider",
    "ModelSettings",
    "Message",
    "MessageRole",
    "TokenUsage",
    "ToolCall",
    "ToolCallChunk",
    "LiteLLMProvider",
    "CostRouter",
    "ModelTier",
    "ProviderCandidate",
    "classify_complexity",
    # Team
    "Team",
    "TeamConfig",
    "TeamProtocol",
    "TeamResult",
    "TeamRunner",
    # Sandbox
    "SandboxConfig",
    "SandboxExecutor",
    "SandboxResult",
    "LocalSandbox",
    # Checkpoint
    "Checkpoint",
    "CheckpointBackend",
    "InMemoryCheckpointBackend",
]

__version__ = "0.1.0"
