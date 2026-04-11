"""EventJournal — 事件日志存储抽象。

提供 append-only 事件日志，支持按 run_id / session_id 查询和回放。
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ckyclaw_framework.events.types import EventType


@dataclass
class EventEntry:
    """单条事件日志。"""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    """全局唯一事件 ID"""

    sequence: int = 0
    """递增序列号（同一 run 内单调递增）"""

    event_type: EventType = EventType.RUN_START
    """事件类型"""

    run_id: str = ""
    """所属运行 ID"""

    session_id: str | None = None
    """所属会话 ID"""

    agent_name: str | None = None
    """相关 Agent 名称"""

    span_id: str | None = None
    """关联的 Span ID（如有）"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """事件时间戳"""

    payload: dict[str, Any] = field(default_factory=dict)
    """事件附加数据（不同类型包含不同内容）"""

    def to_dict(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "span_id": self.span_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


class EventJournal:
    """事件日志存储抽象基类。

    子类实现 _append() 和 _query() 完成持久化。
    """

    async def append(self, entry: EventEntry) -> None:
        """追加一条事件。"""
        await self._append(entry)

    async def append_batch(self, entries: list[EventEntry]) -> None:
        """批量追加事件。"""
        for entry in entries:
            await self._append(entry)

    async def get_events(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        event_types: list[EventType] | None = None,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[EventEntry]:
        """查询事件（按 sequence 升序）。

        Args:
            run_id: 按运行 ID 过滤
            session_id: 按会话 ID 过滤
            event_types: 按事件类型过滤
            after_sequence: 大于此序列号的事件
            limit: 最大返回条数
        """
        return await self._query(
            run_id=run_id,
            session_id=session_id,
            event_types=event_types,
            after_sequence=after_sequence,
            limit=limit,
        )

    async def _append(self, entry: EventEntry) -> None:
        """子类实现：追加事件。"""
        raise NotImplementedError

    async def _query(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        event_types: list[EventType] | None = None,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[EventEntry]:
        """子类实现：查询事件。"""
        raise NotImplementedError


class InMemoryEventJournal(EventJournal):
    """内存事件日志（测试 / 单进程场景使用）。"""

    def __init__(self) -> None:
        self._entries: list[EventEntry] = []
        self._seq_counter = itertools.count(1)
        self._lock = threading.Lock()

    async def _append(self, entry: EventEntry) -> None:
        """追加事件，自动分配递增序列号。"""
        with self._lock:
            entry.sequence = next(self._seq_counter)
            self._entries.append(entry)

    async def _query(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        event_types: list[EventType] | None = None,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[EventEntry]:
        """查询事件。"""
        results = list(self._entries)

        if run_id is not None:
            results = [e for e in results if e.run_id == run_id]
        if session_id is not None:
            results = [e for e in results if e.session_id == session_id]
        if event_types is not None:
            type_set = set(event_types)
            results = [e for e in results if e.event_type in type_set]
        if after_sequence is not None:
            results = [e for e in results if e.sequence > after_sequence]

        results.sort(key=lambda e: e.sequence)

        if limit is not None:
            results = results[:limit]

        return results

    @property
    def size(self) -> int:
        """当前事件数量。"""
        return len(self._entries)

    def clear(self) -> None:
        """清空所有事件。"""
        with self._lock:
            self._entries.clear()
