"""RunHooks — Runner 生命周期钩子定义。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from ckyclaw_framework.model.response import ModelResponse
    from ckyclaw_framework.runner.run_context import RunContext

logger = logging.getLogger(__name__)

# Hook 类型别名
_AsyncHook = Callable[..., Awaitable[None]]


@dataclass
class RunHooks:
    """Runner 生命周期钩子。

    所有 Hook 均为异步函数，Runner 在各触发点 await 调用。
    Hook 异常会被捕获并记录日志，不影响 Agent 执行流（非阻塞语义）。

    用法::

        async def my_run_start(ctx: RunContext) -> None:
            print(f"Run started for agent: {ctx.agent.name}")

        hooks = RunHooks(on_run_start=my_run_start)
        config = RunConfig(hooks=hooks)
        result = await Runner.run(agent, "Hello", config=config)
    """

    on_run_start: _AsyncHook | None = None
    """Run 开始时触发。签名: (ctx: RunContext) -> None"""

    on_run_end: _AsyncHook | None = None
    """Run 结束时触发（成功或失败）。签名: (ctx: RunContext, result: RunResult) -> None"""

    on_agent_start: _AsyncHook | None = None
    """Agent 开始处理时触发（含 Handoff 切换后新 Agent）。签名: (ctx: RunContext, agent_name: str) -> None"""

    on_agent_end: _AsyncHook | None = None
    """Agent 完成处理时触发。签名: (ctx: RunContext, agent_name: str) -> None"""

    on_llm_start: _AsyncHook | None = None
    """LLM 调用发起前触发。签名: (ctx: RunContext, model: str, messages: list[Message]) -> None"""

    on_llm_end: _AsyncHook | None = None
    """LLM 调用返回后触发。签名: (ctx: RunContext, response: ModelResponse) -> None"""

    on_tool_start: _AsyncHook | None = None
    """工具调用执行前触发。签名: (ctx: RunContext, tool_name: str, arguments: dict) -> None"""

    on_tool_end: _AsyncHook | None = None
    """工具调用完成后触发。签名: (ctx: RunContext, tool_name: str, result: str) -> None"""

    on_handoff: _AsyncHook | None = None
    """Agent 间 Handoff 移交时触发。签名: (ctx: RunContext, from_agent: str, to_agent: str) -> None"""

    on_error: _AsyncHook | None = None
    """任何阶段异常时触发。签名: (ctx: RunContext, error: Exception) -> None"""


async def _invoke_hook(hook: _AsyncHook | None, hook_name: str, *args: Any) -> None:
    """安全调用 Hook — 异常捕获 + 日志，不中断执行流。"""
    if hook is None:
        return
    try:
        await hook(*args)
    except Exception:
        logger.exception("Lifecycle hook '%s' raised exception (ignored)", hook_name)
