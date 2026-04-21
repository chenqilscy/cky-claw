"""InMemorySessionBackend — 内存存储后端，用于单元测试和本地开发。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from kasaya.session.session import SessionBackend, SessionMetadata

if TYPE_CHECKING:
    from kasaya.model.message import Message


class InMemorySessionBackend(SessionBackend):
    """内存存储后端——仅用于单元测试和本地开发。进程重启后数据丢失。"""

    def __init__(self) -> None:
        self._messages: dict[str, list[Message]] = {}
        self._metadata: dict[str, SessionMetadata] = {}
        self._lock = asyncio.Lock()

    async def load(self, session_id: str) -> list[Message] | None:
        async with self._lock:
            msgs = self._messages.get(session_id)
            return list(msgs) if msgs is not None else None

    async def save(self, session_id: str, messages: list[Message]) -> None:
        if not messages:
            return
        async with self._lock:
            if session_id not in self._messages:
                self._messages[session_id] = []
                self._metadata[session_id] = SessionMetadata(session_id=session_id)
            self._messages[session_id].extend(messages)
            meta = self._metadata[session_id]
            meta.message_count = len(self._messages[session_id])
            meta.updated_at = datetime.now(UTC)
            # 更新 last_agent_name
            for msg in reversed(messages):
                if msg.agent_name:
                    meta.last_agent_name = msg.agent_name
                    break

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._messages.pop(session_id, None)
            self._metadata.pop(session_id, None)

    async def list_sessions(self, **filters: Any) -> list[SessionMetadata]:
        async with self._lock:
            return list(self._metadata.values())

    async def load_metadata(self, session_id: str) -> SessionMetadata | None:
        async with self._lock:
            return self._metadata.get(session_id)
