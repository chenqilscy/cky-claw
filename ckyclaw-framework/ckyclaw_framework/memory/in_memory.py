"""InMemoryMemoryBackend — 内存存储后端，用于单元测试和本地开发。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ckyclaw_framework.memory.memory import (
    DecayMode,
    MemoryBackend,
    MemoryEntry,
    MemoryType,
    compute_exponential_decay,
)


class InMemoryMemoryBackend(MemoryBackend):
    """内存存储后端——仅用于单元测试和本地开发。进程重启后数据丢失。"""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}  # entry_id → entry
        self._lock = asyncio.Lock()

    async def store(self, user_id: str, entry: MemoryEntry) -> None:
        if not user_id:
            raise ValueError("user_id 不能为空")
        async with self._lock:
            entry.user_id = user_id
            entry.updated_at = datetime.now(UTC)
            if entry.id in self._entries:
                # upsert：保留 created_at
                existing = self._entries[entry.id]
                if existing.user_id != user_id:
                    raise PermissionError("不能修改其他用户的记忆条目")
                entry.created_at = existing.created_at
            self._entries[entry.id] = entry

    async def search(
        self, user_id: str, query: str, *, limit: int = 10
    ) -> list[MemoryEntry]:
        if not query:
            return []
        query_lower = query.lower()
        async with self._lock:
            matched = [
                e
                for e in self._entries.values()
                if e.user_id == user_id and query_lower in e.content.lower()
            ]
            # 按置信度降序 + 更新时间降序排序
            matched.sort(key=lambda e: (-e.confidence, -e.updated_at.timestamp()))
            return matched[:limit]

    async def list_entries(
        self,
        user_id: str,
        *,
        memory_type: MemoryType | None = None,
        agent_name: str | None = None,
    ) -> list[MemoryEntry]:
        async with self._lock:
            entries = [e for e in self._entries.values() if e.user_id == user_id]
            if memory_type is not None:
                entries = [e for e in entries if e.type == memory_type]
            if agent_name is not None:
                entries = [e for e in entries if e.agent_name == agent_name]
            entries.sort(key=lambda e: e.updated_at, reverse=True)
            return entries

    async def get(self, entry_id: str) -> MemoryEntry | None:
        async with self._lock:
            return self._entries.get(entry_id)

    async def delete(self, entry_id: str) -> None:
        async with self._lock:
            self._entries.pop(entry_id, None)

    async def delete_by_user(self, user_id: str) -> int:
        async with self._lock:
            to_delete = [eid for eid, e in self._entries.items() if e.user_id == user_id]
            for eid in to_delete:
                del self._entries[eid]
            return len(to_delete)

    async def decay(
        self,
        before: datetime,
        rate: float,
        *,
        mode: DecayMode = DecayMode.LINEAR,
    ) -> int:
        """对 updated_at < before 的条目降低 confidence。"""
        now = datetime.now(UTC)
        count = 0
        async with self._lock:
            for entry in self._entries.values():
                if entry.updated_at < before:
                    if mode == DecayMode.EXPONENTIAL:
                        days = (now - entry.updated_at).total_seconds() / 86400
                        entry.confidence = compute_exponential_decay(
                            entry.confidence, days, rate
                        )
                    else:
                        entry.confidence = max(0.0, entry.confidence - rate)
                    count += 1
        return count
