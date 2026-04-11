"""MemoryInjector — Runner 调用 LLM 前自动注入相关记忆到上下文。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.memory.memory import MemoryBackend, MemoryEntry, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class MemoryInjectionConfig:
    """记忆注入配置。"""

    max_memory_tokens: int = 1000
    """注入记忆的最大 Token 预算（按字符数/3 估算）。"""

    min_confidence: float = 0.3
    """最低置信度过滤阈值。低于此值的记忆不注入。"""

    inject_types: list[MemoryType] | None = None
    """注入的记忆类型列表。None 表示所有类型。"""

    max_entries: int = 20
    """单次注入最大条目数。"""


class MemoryInjector:
    """记忆注入器。在 Runner 调用 LLM 前检索相关记忆并格式化为 system 消息文本。"""

    def __init__(
        self,
        backend: MemoryBackend,
        config: MemoryInjectionConfig | None = None,
    ) -> None:
        self._backend = backend
        self._config = config or MemoryInjectionConfig()

    async def build_memory_context(self, user_id: str, query: str) -> str:
        """检索相关记忆，格式化为可注入 system 消息的文本。

        Args:
            user_id: 用户标识。
            query: 检索查询（通常是最新用户消息）。

        Returns:
            格式化的记忆文本。空字符串表示无可用记忆。
        """
        if not user_id:
            return ""

        try:
            entries = await self._backend.search(
                user_id, query, limit=self._config.max_entries
            )
        except Exception:
            logger.exception("Memory search failed for user=%s", user_id)
            return ""

        # 过滤低置信度 + 类型过滤
        filtered = self._filter_entries(entries)
        if not filtered:
            return ""

        # Token 预算内格式化
        return self._format_entries(filtered)

    def _filter_entries(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """过滤低置信度和不匹配类型的记忆。"""
        result: list[MemoryEntry] = []
        for entry in entries:
            if entry.confidence < self._config.min_confidence:
                continue
            if self._config.inject_types is not None and entry.type not in self._config.inject_types:
                continue
            result.append(entry)
        return result

    def _format_entries(self, entries: list[MemoryEntry]) -> str:
        """格式化记忆条目为文本，尊重 Token 预算。"""
        lines: list[str] = ["## 用户记忆"]
        budget = self._config.max_memory_tokens * 3  # token → chars 估算
        used = len(lines[0])

        type_labels = {
            "user_profile": "用户档案",
            "history_summary": "历史摘要",
            "structured_fact": "事实",
        }

        for entry in entries:
            label = type_labels.get(entry.type.value, entry.type.value)
            line = f"- [{label}] {entry.content}（置信度: {entry.confidence:.2f}）"
            line_chars = len(line)
            if used + line_chars > budget:
                break
            lines.append(line)
            used += line_chars

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)
