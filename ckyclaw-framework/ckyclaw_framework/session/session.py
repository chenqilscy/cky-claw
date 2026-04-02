"""Session — 会话管理器。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message


@dataclass
class SessionMetadata:
    """Session 元信息。"""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    total_tokens: int = 0
    last_agent_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class SessionBackend(ABC):
    """Session 存储后端抽象。"""

    @abstractmethod
    async def load(self, session_id: str) -> list[Message] | None:
        """加载会话历史消息。"""
        ...

    @abstractmethod
    async def save(self, session_id: str, messages: list[Message]) -> None:
        """追加保存新消息。"""
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """删除会话。"""
        ...

    @abstractmethod
    async def list_sessions(self, **filters: Any) -> list[SessionMetadata]:
        """列出会话（支持过滤）。"""
        ...

    @abstractmethod
    async def load_metadata(self, session_id: str) -> SessionMetadata | None:
        """加载会话元数据。"""
        ...


@dataclass
class Session:
    """会话管理器——自动处理多轮对话的历史存储与加载。"""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    backend: SessionBackend | None = None
    metadata: SessionMetadata | None = None

    async def get_history(self) -> list[Message]:
        """获取完整历史。"""
        if self.backend is None:
            return []
        return await self.backend.load(self.session_id) or []

    async def append(self, messages: list[Message]) -> None:
        """追加消息。"""
        if self.backend is not None:
            await self.backend.save(self.session_id, messages)

    async def clear(self) -> None:
        """清空历史。"""
        if self.backend is not None:
            await self.backend.delete(self.session_id)
