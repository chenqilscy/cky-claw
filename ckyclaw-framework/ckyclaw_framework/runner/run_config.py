"""RunConfig — 运行时配置覆盖。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ckyclaw_framework.approval.handler import ApprovalHandler
    from ckyclaw_framework.approval.mode import ApprovalMode
    from ckyclaw_framework.model.provider import ModelProvider
    from ckyclaw_framework.model.settings import ModelSettings
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

    on_max_turns_exceeded: Callable | None = None
    """超过 max_turns 时的回调"""

    on_agent_start: Callable | None = None
    on_agent_end: Callable | None = None
    on_tool_call: Callable | None = None
    on_handoff: Callable | None = None

    approval_mode: ApprovalMode | None = None
    """全局覆盖 Agent 的审批模式"""

    approval_handler: ApprovalHandler | None = None
    """审批处理器实例。suggest/auto-edit 模式下必须提供。"""
