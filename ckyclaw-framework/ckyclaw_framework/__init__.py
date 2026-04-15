"""CkyClaw Framework — Python Agent 运行时框架"""

from __future__ import annotations

from ckyclaw_framework.a2a.adapter import A2AAdapter

# === A2A ===
from ckyclaw_framework.a2a.agent_card import AgentCapability, AgentCard, AgentSkillCard
from ckyclaw_framework.a2a.client import A2AClient, A2AClientError
from ckyclaw_framework.a2a.server import A2AServer
from ckyclaw_framework.a2a.task import A2ATask, TaskArtifact, TaskState, TaskStatus

# === Core ===
from ckyclaw_framework.agent.agent import Agent, InstructionsType
from ckyclaw_framework.approval.handler import ApprovalHandler

# === Approval ===
from ckyclaw_framework.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError

# === Checkpoint ===
from ckyclaw_framework.checkpoint import Checkpoint, CheckpointBackend, InMemoryCheckpointBackend

# === Compat (OpenAI Agents SDK) ===
from ckyclaw_framework.compat.adapter import (
    SdkAgentAdapter,
    from_openai_agent,
    from_openai_guardrail,
    from_openai_handoff,
    from_openai_tool,
)

# === Debug ===
from ckyclaw_framework.debug.controller import (
    DebugController,
    DebugEvent,
    DebugEventType,
    DebugMode,
    DebugState,
    DebugStoppedError,
    PauseContext,
)

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
from ckyclaw_framework.guardrails.content_safety_guardrail import ContentSafetyGuardrail

# === Guardrails ===
from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
from ckyclaw_framework.guardrails.llm_guardrail import LLMGuardrail
from ckyclaw_framework.guardrails.max_token_guardrail import MaxTokenGuardrail
from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
from ckyclaw_framework.guardrails.pii_guardrail import PIIDetectionGuardrail
from ckyclaw_framework.guardrails.prompt_injection_guardrail import PromptInjectionGuardrail
from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail
from ckyclaw_framework.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
from ckyclaw_framework.guardrails.tool_whitelist_guardrail import ToolWhitelistGuardrail

# === Orchestration ===
from ckyclaw_framework.handoff.handoff import Handoff, InputFilter

# === Intent Detection ===
from ckyclaw_framework.intent import IntentDetector, IntentSignal, KeywordIntentDetector
from ckyclaw_framework.memory.hooks import MemoryExtractionHook
from ckyclaw_framework.memory.in_memory import InMemoryMemoryBackend

# === Memory ===
from ckyclaw_framework.memory.memory import DecayMode, MemoryBackend, MemoryEntry, MemoryType, compute_exponential_decay
from ckyclaw_framework.memory.retriever import MemoryRetriever
from ckyclaw_framework.model.content_block import (
    AudioContent,
    ContentBlock,
    ContentType,
    FileContent,
    ImageContent,
    TextContent,
    content_block_from_dict,
    content_blocks_to_litellm,
    content_blocks_to_text,
)
from ckyclaw_framework.model.cost_router import CostRouter, ModelTier, ProviderCandidate, classify_complexity
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage

# === Model ===
from ckyclaw_framework.model.provider import ModelProvider, ToolCall, ToolCallChunk
from ckyclaw_framework.model.settings import ModelSettings

# === RAG ===
from ckyclaw_framework.rag import (
    Chunk,
    ChunkStrategy,
    Document,
    DocumentLoader,
    EmbeddingProvider,
    FixedSizeChunker,
    InMemoryEmbeddingProvider,
    InMemoryVectorStore,
    MarkdownChunker,
    RAGPipeline,
    RAGResult,
    RecursiveCharacterChunker,
    SearchResult,
    TextLoader,
    VectorStore,
    create_knowledge_base_tool,
)
from ckyclaw_framework.runner.result import RunResult, StreamEvent
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.run_context import RunContext
from ckyclaw_framework.runner.runner import Runner

# === Sandbox ===
from ckyclaw_framework.sandbox.config import SandboxConfig
from ckyclaw_framework.sandbox.executor import SandboxExecutor, SandboxResult
from ckyclaw_framework.sandbox.local_sandbox import LocalSandbox
from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimmer, HistoryTrimStrategy
from ckyclaw_framework.session.in_memory import InMemorySessionBackend

# === Session ===
from ckyclaw_framework.session.session import Session, SessionBackend, SessionMetadata
from ckyclaw_framework.skills.injector import SkillInjector
from ckyclaw_framework.skills.registry import SkillNotFoundError, SkillRegistry

# === Skills ===
from ckyclaw_framework.skills.skill import Skill, SkillCategory

# === Team ===
from ckyclaw_framework.team.protocol import TeamProtocol
from ckyclaw_framework.team.team import Team, TeamConfig
from ckyclaw_framework.team.team_runner import TeamResult, TeamRunner

# === Tools ===
from ckyclaw_framework.tools.function_tool import FunctionTool, function_tool
from ckyclaw_framework.tools.tool_context import ToolContext
from ckyclaw_framework.tracing.console_processor import ConsoleTraceProcessor
from ckyclaw_framework.tracing.processor import TraceProcessor
from ckyclaw_framework.tracing.span import Span, SpanStatus, SpanType

# === Tracing ===
from ckyclaw_framework.tracing.trace import Trace
from ckyclaw_framework.workflow.config import WorkflowRunConfig

# === Workflow ===
from ckyclaw_framework.workflow.engine import AgentNotFoundError, AgentResolver, WorkflowEngine
from ckyclaw_framework.workflow.evaluator import UnsafeExpressionError, evaluate
from ckyclaw_framework.workflow.result import StepResult, WorkflowResult, WorkflowStatus
from ckyclaw_framework.workflow.step import (
    AgentStep,
    BranchCondition,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    RetryConfig,
    Step,
    StepIO,
    StepStatus,
    StepType,
)
from ckyclaw_framework.workflow.validator import (
    WorkflowValidationError,
    topological_sort,
    validate_workflow,
    validate_workflow_strict,
)
from ckyclaw_framework.workflow.workflow import Edge, Workflow

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
    # Debug
    "DebugController",
    "DebugEvent",
    "DebugEventType",
    "DebugMode",
    "DebugState",
    "DebugStoppedError",
    "PauseContext",
    # Intent Detection
    "IntentDetector",
    "IntentSignal",
    "KeywordIntentDetector",
    # RAG
    "Document",
    "DocumentLoader",
    "TextLoader",
    "Chunk",
    "ChunkStrategy",
    "FixedSizeChunker",
    "MarkdownChunker",
    "RecursiveCharacterChunker",
    "EmbeddingProvider",
    "InMemoryEmbeddingProvider",
    "VectorStore",
    "InMemoryVectorStore",
    "SearchResult",
    "RAGPipeline",
    "RAGResult",
    "create_knowledge_base_tool",
    # ContentBlock (Multi-Modal)
    "ContentType",
    "TextContent",
    "ImageContent",
    "AudioContent",
    "FileContent",
    "ContentBlock",
    "content_block_from_dict",
    "content_blocks_to_text",
    "content_blocks_to_litellm",
    # Evolution
    "EvolutionConfig",
    "EvolutionProposal",
    "ProposalStatus",
    "ProposalType",
    "EvolutionSignal",
    "FeedbackSignal",
    "MetricSignal",
    "SignalCollector",
    "SignalType",
    "ToolPerformanceSignal",
    "EvolutionStrategy",
    "StrategyEngine",
    # A2A (Agent-to-Agent Protocol)
    "AgentCard",
    "AgentCapability",
    "AgentSkillCard",
    "A2ATask",
    "TaskArtifact",
    "TaskState",
    "TaskStatus",
    "A2AClient",
    "A2AClientError",
    "A2AServer",
    "A2AAdapter",
    # Compat (OpenAI Agents SDK)
    "SdkAgentAdapter",
    "from_openai_agent",
    "from_openai_guardrail",
    "from_openai_handoff",
    "from_openai_tool",
]

__version__ = "0.1.0"
