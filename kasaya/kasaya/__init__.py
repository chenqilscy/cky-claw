"""Kasaya Framework — Python Agent 运行时框架"""

from __future__ import annotations

from kasaya.a2a.adapter import A2AAdapter

# === A2A ===
from kasaya.a2a.agent_card import AgentCapability, AgentCard, AgentSkillCard
from kasaya.a2a.client import A2AClient, A2AClientError
from kasaya.a2a.server import A2AServer
from kasaya.a2a.task import A2ATask, TaskArtifact, TaskState, TaskStatus

# === Core ===
from kasaya.agent.agent import Agent, InstructionsType
from kasaya.approval.handler import ApprovalHandler

# === Approval ===
from kasaya.approval.mode import ApprovalDecision, ApprovalMode, ApprovalRejectedError

# === Checkpoint ===
from kasaya.checkpoint import Checkpoint, CheckpointBackend, InMemoryCheckpointBackend

# === Compat (OpenAI Agents SDK) ===
from kasaya.compat.adapter import (
    SdkAgentAdapter,
    from_openai_agent,
    from_openai_guardrail,
    from_openai_handoff,
    from_openai_tool,
)

# === Debug ===
from kasaya.debug.controller import (
    DebugController,
    DebugEvent,
    DebugEventType,
    DebugMode,
    DebugState,
    DebugStoppedError,
    PauseContext,
)

# === Evolution ===
from kasaya.evolution.config import EvolutionConfig
from kasaya.evolution.proposal import EvolutionProposal, ProposalStatus, ProposalType
from kasaya.evolution.signals import (
    EvolutionSignal,
    FeedbackSignal,
    MetricSignal,
    SignalCollector,
    SignalType,
    ToolPerformanceSignal,
)
from kasaya.evolution.strategy import EvolutionStrategy, StrategyEngine
from kasaya.guardrails.content_safety_guardrail import ContentSafetyGuardrail

# === Guardrails ===
from kasaya.guardrails.input_guardrail import InputGuardrail
from kasaya.guardrails.llm_guardrail import LLMGuardrail
from kasaya.guardrails.max_token_guardrail import MaxTokenGuardrail
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.pii_guardrail import PIIDetectionGuardrail
from kasaya.guardrails.prompt_injection_guardrail import PromptInjectionGuardrail
from kasaya.guardrails.regex_guardrail import RegexGuardrail
from kasaya.guardrails.result import (
    GuardrailResult,
    InputGuardrailTripwireError,
    OutputGuardrailTripwireError,
)
from kasaya.guardrails.tool_guardrail import ToolGuardrail
from kasaya.guardrails.tool_whitelist_guardrail import ToolWhitelistGuardrail

# === Orchestration ===
from kasaya.handoff.handoff import Handoff, InputFilter

# === Intent Detection ===
from kasaya.intent import IntentDetector, IntentSignal, KeywordIntentDetector
from kasaya.memory.hooks import MemoryExtractionHook
from kasaya.memory.in_memory import InMemoryMemoryBackend

# === Memory ===
from kasaya.memory.memory import DecayMode, MemoryBackend, MemoryEntry, MemoryType, compute_exponential_decay
from kasaya.memory.retriever import MemoryRetriever
from kasaya.model.content_block import (
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
from kasaya.model.cost_router import CostRouter, ModelTier, ProviderCandidate, classify_complexity
from kasaya.model.litellm_provider import LiteLLMProvider
from kasaya.model.message import Message, MessageRole, TokenUsage

# === Model ===
from kasaya.model.provider import ModelProvider, ToolCall, ToolCallChunk
from kasaya.model.settings import ModelSettings

# === RAG ===
from kasaya.rag import (
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
from kasaya.runner.result import RunResult, StreamEvent
from kasaya.runner.run_config import RunConfig
from kasaya.runner.run_context import RunContext
from kasaya.runner.runner import Runner

# === Sandbox ===
from kasaya.sandbox.config import SandboxConfig
from kasaya.sandbox.executor import SandboxExecutor, SandboxResult
from kasaya.sandbox.local_sandbox import LocalSandbox
from kasaya.session.history_trimmer import HistoryTrimConfig, HistoryTrimmer, HistoryTrimStrategy
from kasaya.session.in_memory import InMemorySessionBackend

# === Session ===
from kasaya.session.session import Session, SessionBackend, SessionMetadata
from kasaya.skills.injector import SkillInjector
from kasaya.skills.registry import SkillNotFoundError, SkillRegistry

# === Skills ===
from kasaya.skills.skill import Skill, SkillCategory

# === Team ===
from kasaya.team.protocol import TeamProtocol
from kasaya.team.team import Team, TeamConfig
from kasaya.team.team_runner import TeamResult, TeamRunner

# === Tools ===
from kasaya.tools.function_tool import FunctionTool, function_tool
from kasaya.tools.tool_context import ToolContext
from kasaya.tracing.console_processor import ConsoleTraceProcessor
from kasaya.tracing.processor import TraceProcessor
from kasaya.tracing.span import Span, SpanStatus, SpanType

# === Tracing ===
from kasaya.tracing.trace import Trace
from kasaya.workflow.config import WorkflowRunConfig

# === Workflow ===
from kasaya.workflow.engine import AgentNotFoundError, AgentResolver, WorkflowEngine
from kasaya.workflow.evaluator import UnsafeExpressionError, evaluate
from kasaya.workflow.result import StepResult, WorkflowResult, WorkflowStatus
from kasaya.workflow.step import (
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
from kasaya.workflow.validator import (
    WorkflowValidationError,
    topological_sort,
    validate_workflow,
    validate_workflow_strict,
)
from kasaya.workflow.workflow import Edge, Workflow

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
