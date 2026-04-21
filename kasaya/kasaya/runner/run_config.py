"""RunConfig — 运行时配置覆盖。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from kasaya.approval.handler import ApprovalHandler
    from kasaya.approval.mode import ApprovalMode
    from kasaya.artifacts.store import ArtifactStore
    from kasaya.checkpoint import CheckpointBackend
    from kasaya.debug.controller import DebugController
    from kasaya.events.journal import EventJournal
    from kasaya.guardrails.input_guardrail import InputGuardrail
    from kasaya.guardrails.output_guardrail import OutputGuardrail
    from kasaya.guardrails.tool_guardrail import ToolGuardrail
    from kasaya.intent import IntentDetector
    from kasaya.memory.injector import MemoryInjectionConfig
    from kasaya.memory.memory import MemoryBackend
    from kasaya.model.circuit_breaker import CircuitBreaker
    from kasaya.model.fallback import FallbackChainProvider
    from kasaya.model.provider import ModelProvider
    from kasaya.model.settings import ModelSettings
    from kasaya.runner.cancellation import CancellationToken
    from kasaya.runner.hooks import RunHooks
    from kasaya.session.history_trimmer import HistoryTrimStrategy
    from kasaya.session.session import SessionBackend
    from kasaya.tools.middleware import ToolMiddleware
    from kasaya.tracing.processor import TraceProcessor


@dataclass
class RunConfig:
    """运行时配置覆盖——不修改 Agent 定义。"""

    model: str | None = None
    """全局覆盖 Agent 的模型"""

    model_settings: ModelSettings | None = None
    """全局覆盖模型参数"""

    model_provider: ModelProvider | None = None
    """自定义模型提供商实例"""

    tracing_enabled: bool = True
    """是否启用链路追踪"""

    workflow_name: str = "default"
    """工作流名称（用于 Trace 分组）"""

    trace_include_sensitive_data: bool = True
    """是否记录 LLM 和工具的输入/输出"""

    trace_processors: list[TraceProcessor] = field(default_factory=list)
    """追踪处理器列表"""

    session_backend: SessionBackend | None = None
    """Session 存储后端"""

    max_history_tokens: int | None = None
    """Context Window 历史 Token 预算。设置后自动裁剪 Session 历史。"""

    max_history_messages: int | None = None
    """历史消息条数上限。设置后自动裁剪 Session 历史。"""

    history_trim_strategy: HistoryTrimStrategy | None = None
    """历史裁剪策略。默认 TOKEN_BUDGET。"""

    on_max_turns_exceeded: Callable[..., Any] | None = None
    """超过 max_turns 时的回调"""

    hooks: RunHooks | None = None
    """生命周期钩子。Runner 在各关键节点调用对应 Hook（非阻塞）。"""

    approval_mode: ApprovalMode | None = None
    """全局覆盖 Agent 的审批模式"""

    approval_handler: ApprovalHandler | None = None
    """审批处理器实例。suggest/auto-edit 模式下必须提供。"""

    input_guardrails: list[InputGuardrail] = field(default_factory=list)
    """追加运行级输入护栏（追加到 Agent 级之后执行）"""

    output_guardrails: list[OutputGuardrail] = field(default_factory=list)
    """追加运行级输出护栏（追加到 Agent 级之后执行）"""

    tool_guardrails: list[ToolGuardrail] = field(default_factory=list)
    """追加运行级工具护栏（追加到 Agent 级之后执行）"""

    tool_timeout: float | None = None
    """全局工具执行超时（秒）。当 FunctionTool 未设置自身 timeout 时生效。"""

    max_tool_concurrency: int | None = None
    """工具并行执行的最大并发数。None 表示无限制。设置后使用 Semaphore 限流。"""

    guardrail_parallel: bool = False
    """是否启用 Guardrail 并行执行模式。True 时所有 Guardrail 并发执行，False 时串行短路。"""

    locale: str | None = None
    """用户语言偏好（BCP 47 格式，如 'zh-CN'、'en-US'）。用于 Agent 多语言 Instructions 解析。"""

    max_retries: int = 0
    """LLM API 调用失败时的最大重试次数（0 表示不重试）。"""

    retry_delay: float = 1.0
    """重试间隔基数（秒）。实际延迟 = retry_delay * 2^(attempt-1)（指数退避）。"""

    checkpoint_backend: CheckpointBackend | None = None
    """Checkpoint 存储后端。配置后 Runner 在每个 turn 结束时自动保存中间状态。"""

    checkpoint_interval: int = 1
    """每 N 个 turn 保存一次 checkpoint。默认每轮都保存。"""

    intent_detector: IntentDetector | None = None
    """意图飘移检测器。配置后 Runner 在每次 LLM 回复后自动检测飘移。"""

    drift_threshold: float = 0.6
    """意图飘移阈值（0~1）。drift_score >= 此值时触发 on_intent_drift Hook。"""

    debug_controller: DebugController | None = None
    """调试控制器。配置后 Runner 在每轮 LLM 后、工具调用前、Handoff 前调用 checkpoint()，
    DebugController 决定是否暂停执行。用于交互式单步调试 Agent 执行流程。"""

    artifact_store: ArtifactStore | None = None
    """Artifact 存储后端。配置后 Runner 将超大工具结果外部化到 ArtifactStore，
    上下文中只保留摘要 + artifact_id 引用，节约 Token 预算。"""

    artifact_threshold: int = 5000
    """工具结果 Token 阈值。估算 Token 数超过此值时触发 Artifact 外部化。"""

    max_tool_result_chars: int | None = None
    """工具结果字符数硬上限。超出时直接截断（在 Artifact 外部化之后生效）。
    None 表示不截断。"""

    system_prompt_prefix: str | None = None
    """稳定的系统提示前缀。配置后作为独立 system 消息置于 Agent instructions 之前，
    标记 cache_control 元数据以最大化 LLM KV 缓存命中率（Anthropic/OpenAI prefix caching）。
    适合放入不随对话变化的全局指令、公司规范等。"""

    memory_backend: MemoryBackend | None = None
    """记忆存储后端。配置后 Runner 在每次 LLM 调用前自动检索并注入相关记忆到 system 消息。"""

    memory_user_id: str | None = None
    """记忆所属用户 ID。配合 memory_backend 使用。不设置时不注入记忆。"""

    memory_injection_config: MemoryInjectionConfig | None = None
    """记忆注入配置。不设置时使用 MemoryInjectionConfig 默认值。"""

    circuit_breaker: CircuitBreaker | None = None
    """LLM 调用熔断器。配置后在 provider.chat() 外层包装熔断逻辑，
    连续失败超过阈值时自动切换到 OPEN 状态拒绝请求。"""

    fallback_provider: FallbackChainProvider | None = None
    """Provider 降级链。配置后替代 model_provider 使用，自动多级降级。
    与 circuit_breaker 互斥——FallbackChainProvider 内部自带 per-entry CircuitBreaker。"""

    tool_middleware: list[ToolMiddleware] = field(default_factory=list)
    """工具执行中间件管道（追加到 Agent 级之后执行）。
    按顺序执行 before_execute，逆序执行 after_execute（洋葱模型）。"""

    event_journal: EventJournal | None = None
    """事件日志。配置后自动创建 EventJournalProcessor 注入 trace_processors，
    将 Trace/Span 生命周期事件转化为细粒度 EventEntry 并写入 Journal。"""

    cancel_token: CancellationToken | None = None
    """取消令牌。配置后 Runner 在每次 LLM 调用和工具执行前检查令牌状态，
    已取消时抛出 asyncio.CancelledError 终止执行。支持父子级联取消。"""

    template_variables: dict[str, Any] | None = None
    """模板变量值。配置后 Runner 在构建 system 消息时，自动将 Agent instructions
    中的 {{variable}} 占位符替换为对应值。变量值中的 {{ 和 }} 会被转义防止注入。"""

    environment: str | None = None
    """运行环境标识（如 'dev'、'staging'、'prod'）。配置后 Runner 在 Trace 中
    记录环境信息，上层可根据此字段加载环境特定的 Agent 绑定配置。"""
