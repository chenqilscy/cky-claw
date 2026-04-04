"""RunConfig — 运行时配置覆盖。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ckyclaw_framework.approval.handler import ApprovalHandler
    from ckyclaw_framework.approval.mode import ApprovalMode
    from ckyclaw_framework.guardrails.input_guardrail import InputGuardrail
    from ckyclaw_framework.guardrails.output_guardrail import OutputGuardrail
    from ckyclaw_framework.guardrails.tool_guardrail import ToolGuardrail
    from ckyclaw_framework.model.provider import ModelProvider
    from ckyclaw_framework.model.settings import ModelSettings
    from ckyclaw_framework.runner.hooks import RunHooks
    from ckyclaw_framework.session.history_trimmer import HistoryTrimStrategy
    from ckyclaw_framework.session.session import SessionBackend
    from ckyclaw_framework.tracing.processor import TraceProcessor


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

    max_retries: int = 0
    """LLM API 调用失败时的最大重试次数（0 表示不重试）。"""

    retry_delay: float = 1.0
    """重试间隔基数（秒）。实际延迟 = retry_delay * 2^(attempt-1)（指数退避）。"""
