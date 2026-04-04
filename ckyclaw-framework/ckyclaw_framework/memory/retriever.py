"""MemoryRetriever — 记忆检索与注入。"""

from __future__ import annotations

from ckyclaw_framework.memory.memory import MemoryBackend, MemoryEntry, MemoryType

# 记忆类型中文标签
_TYPE_LABELS: dict[MemoryType, str] = {
    MemoryType.USER_PROFILE: "用户档案",
    MemoryType.HISTORY_SUMMARY: "历史摘要",
    MemoryType.STRUCTURED_FACT: "事实",
}


class MemoryRetriever:
    """检索相关记忆并格式化为可注入系统消息的文本。

    与 Runner 解耦——由上层（Backend Service）在调用 Runner 前使用。
    """

    def __init__(
        self,
        backend: MemoryBackend,
        max_memory_tokens: int = 1000,
        min_confidence: float = 0.3,
    ) -> None:
        self._backend = backend
        self._max_memory_tokens = max_memory_tokens
        self._min_confidence = min_confidence

    async def retrieve(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """检索用户的相关记忆条目。

        过滤掉置信度低于阈值的条目。
        """
        entries = await self._backend.search(user_id, query, limit=limit)
        return [e for e in entries if e.confidence >= self._min_confidence]

    def format_for_injection(self, entries: list[MemoryEntry]) -> str:
        """将记忆条目格式化为可注入 System Message 的文本。

        控制总字符数近似不超过 max_memory_tokens × 4（粗略 token→char 估算）。

        Returns:
            格式化后的记忆文本。如果没有条目，返回空字符串。
        """
        if not entries:
            return ""

        lines: list[str] = ["## 用户记忆"]
        char_budget = self._max_memory_tokens * 4  # 粗略估算
        used = len(lines[0])

        for entry in entries:
            label = _TYPE_LABELS.get(entry.type, entry.type.value)
            line = f"- [{label}] {entry.content}（置信度: {entry.confidence:.2f}）"
            if used + len(line) + 1 > char_budget:
                break
            lines.append(line)
            used += len(line) + 1  # +1 for newline

        return "\n".join(lines) if len(lines) > 1 else ""
