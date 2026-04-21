"""记忆提取钩子 — 在 Agent 执行完成后自动提取与存储记忆。

MemoryExtractionHook 实现 RunHooks 接口，在 on_run_end 触发时
自动从 Agent 输出中提取记忆条目并存储到 MemoryBackend。

用法::

    from kasaya.memory import MemoryExtractionHook, InMemoryMemoryBackend

    backend = InMemoryMemoryBackend()
    hook = MemoryExtractionHook(backend, user_id="user-1")
    config = RunConfig(hooks=hook.as_run_hooks())
    result = await Runner.run(agent, "Hello", config=config)
    # backend 中已自动存储从输出提取的记忆
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kasaya.memory.memory import MemoryBackend, MemoryEntry, MemoryType
from kasaya.runner.hooks import RunHooks

if TYPE_CHECKING:
    from collections.abc import Callable

    from kasaya.runner.result import RunResult
    from kasaya.runner.run_context import RunContext

logger = logging.getLogger(__name__)

# 默认最小输出长度，过短的输出不提取记忆
_DEFAULT_MIN_OUTPUT_LENGTH = 50

# 默认新记忆的置信度
_DEFAULT_CONFIDENCE = 0.7


@dataclass
class MemoryExtractionHook:
    """自动记忆提取钩子。

    在 Agent Run 结束后，将有价值的输出自动存储为 STRUCTURED_FACT 记忆。

    Attributes:
        backend: 记忆存储后端。
        user_id: 目标用户 ID（所有提取的记忆归属此用户）。
        min_output_length: 输出文本最小长度，低于此值不提取。
        default_confidence: 新记忆的默认置信度。
        extract_fn: 自定义提取函数，签名 (output: str, agent_name: str) -> list[str]。
            返回要存储的记忆文本列表。为 None 时使用默认提取逻辑（直接存储输出）。
    """

    backend: MemoryBackend
    """记忆存储后端实例。"""

    user_id: str = ""
    """目标用户 ID。"""

    min_output_length: int = _DEFAULT_MIN_OUTPUT_LENGTH
    """输出文本最小长度阈值。"""

    default_confidence: float = _DEFAULT_CONFIDENCE
    """新记忆的默认置信度。"""

    extract_fn: Callable[[str, str], list[str]] | None = None
    """自定义记忆提取函数。返回待存储的记忆文本列表。"""

    _session_id: str | None = field(default=None, repr=False)
    """当前会话 ID（从 RunContext 获取）。"""

    _agent_name: str = field(default="", repr=False)
    """最终处理的 Agent 名称。"""

    _extracted_count: int = field(default=0, repr=False)
    """累计提取的记忆条数。"""

    async def _on_agent_start(self, ctx: RunContext, agent_name: str) -> None:
        """记录当前 Agent 名称。"""
        self._agent_name = agent_name

    async def _on_run_end(self, ctx: RunContext, result: RunResult) -> None:
        """Run 结束时提取并存储记忆。"""
        if not self.user_id:
            logger.debug("MemoryExtractionHook: user_id 为空，跳过记忆提取")
            return

        output = str(result.output) if result.output else ""
        if len(output) < self.min_output_length:
            logger.debug(
                "MemoryExtractionHook: 输出长度 %d < %d，跳过",
                len(output),
                self.min_output_length,
            )
            return

        agent_name = result.last_agent_name or self._agent_name or ctx.agent.name

        # 使用自定义提取函数或默认逻辑
        texts = self.extract_fn(output, agent_name) if self.extract_fn is not None else [output]

        for text in texts:
            if not text or len(text) < self.min_output_length:
                continue
            entry = MemoryEntry(
                type=MemoryType.STRUCTURED_FACT,
                content=text[:10000],  # 限制最大长度
                confidence=self.default_confidence,
                user_id=self.user_id,
                agent_name=agent_name,
                source_session_id=self._session_id,
            )
            try:
                await self.backend.store(self.user_id, entry)
                self._extracted_count += 1
            except Exception:
                logger.exception("MemoryExtractionHook: 存储记忆失败")

    def as_run_hooks(self) -> RunHooks:
        """转换为 RunHooks 实例。"""
        return RunHooks(
            on_agent_start=self._on_agent_start,
            on_run_end=self._on_run_end,
        )

    @property
    def extracted_count(self) -> int:
        """累计提取的记忆条数。"""
        return self._extracted_count
