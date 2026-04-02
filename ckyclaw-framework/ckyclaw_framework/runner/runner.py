"""Runner — Agent 执行引擎，驱动 Agent Loop 完成推理和工具调用。"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from ckyclaw_framework.agent.agent import Agent
    from ckyclaw_framework.model.message import Message
    from ckyclaw_framework.runner.result import RunResult, StreamEvent
    from ckyclaw_framework.runner.run_config import RunConfig
    from ckyclaw_framework.session.session import Session


class Runner:
    """Agent 执行引擎。驱动 Agent Loop 完成推理和工具调用。"""

    @staticmethod
    async def run(
        agent: Agent,
        input: str | list[Message],
        *,
        session: Session | None = None,
        config: RunConfig | None = None,
        context: dict | None = None,
        max_turns: int = 10,
    ) -> RunResult:
        """异步运行 Agent。"""
        raise NotImplementedError

    @staticmethod
    def run_sync(
        agent: Agent,
        input: str | list[Message],
        **kwargs: object,
    ) -> RunResult:
        """同步运行（内部使用 asyncio.run）。"""
        raise NotImplementedError

    @staticmethod
    async def run_streamed(
        agent: Agent,
        input: str | list[Message],
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        """异步流式运行。逐步产出 StreamEvent。"""
        raise NotImplementedError
        yield  # noqa: unreachable — make this an async generator
