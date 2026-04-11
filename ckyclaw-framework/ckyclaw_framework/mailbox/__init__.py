"""Mailbox — Agent 间持久化通信。

提供基于消息队列的 Agent 间异步通信机制：
- MailboxMessage: 消息数据类
- MailboxBackend: 存储后端抽象
- InMemoryMailboxBackend: 内存实现
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MailboxMessage:
    """Agent 间通信消息。"""

    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    """消息唯一标识。"""

    run_id: str = ""
    """所属运行 ID。"""

    from_agent: str = ""
    """发送方 Agent 名称。"""

    to_agent: str = ""
    """接收方 Agent 名称。"""

    content: str = ""
    """消息内容。"""

    message_type: str = "handoff"
    """消息类型：handoff（交接）/ notification（通知）/ request（请求）。"""

    is_read: bool = False
    """是否已读。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """扩展元数据。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """创建时间。"""


class MailboxBackend(ABC):
    """Mailbox 存储后端抽象。"""

    @abstractmethod
    async def send(self, message: MailboxMessage) -> None:
        """发送消息到邮箱。

        Args:
            message: 要发送的消息。
        """
        ...

    @abstractmethod
    async def receive(self, agent_name: str, *, run_id: str | None = None, unread_only: bool = True) -> list[MailboxMessage]:
        """接收指定 Agent 的消息。

        Args:
            agent_name: 接收方 Agent 名称。
            run_id: 可选，按 run_id 过滤。
            unread_only: 是否仅返回未读消息。

        Returns:
            消息列表（按时间升序）。
        """
        ...

    @abstractmethod
    async def mark_read(self, message_id: str) -> None:
        """标记消息为已读。

        Args:
            message_id: 消息 ID。
        """
        ...

    @abstractmethod
    async def get_conversation(self, run_id: str, agent_a: str, agent_b: str) -> list[MailboxMessage]:
        """获取两个 Agent 之间的对话历史。

        Args:
            run_id: 运行 ID。
            agent_a: Agent A 名称。
            agent_b: Agent B 名称。

        Returns:
            双向消息列表（按时间升序）。
        """
        ...

    @abstractmethod
    async def delete_run_messages(self, run_id: str) -> None:
        """删除指定 Run 的所有消息。

        Args:
            run_id: 运行 ID。
        """
        ...


class InMemoryMailboxBackend(MailboxBackend):
    """内存 Mailbox 后端（用于测试和开发）。"""

    def __init__(self) -> None:
        self._messages: list[MailboxMessage] = []

    async def send(self, message: MailboxMessage) -> None:
        """发送消息。"""
        self._messages.append(message)

    async def receive(self, agent_name: str, *, run_id: str | None = None, unread_only: bool = True) -> list[MailboxMessage]:
        """接收消息。"""
        results = []
        for msg in self._messages:
            if msg.to_agent != agent_name:
                continue
            if run_id is not None and msg.run_id != run_id:
                continue
            if unread_only and msg.is_read:
                continue
            results.append(msg)
        return sorted(results, key=lambda m: m.created_at)

    async def mark_read(self, message_id: str) -> None:
        """标记已读。"""
        for msg in self._messages:
            if msg.message_id == message_id:
                msg.is_read = True
                return

    async def get_conversation(self, run_id: str, agent_a: str, agent_b: str) -> list[MailboxMessage]:
        """获取对话历史。"""
        results = []
        for msg in self._messages:
            if msg.run_id != run_id:
                continue
            if (msg.from_agent == agent_a and msg.to_agent == agent_b) or \
               (msg.from_agent == agent_b and msg.to_agent == agent_a):
                results.append(msg)
        return sorted(results, key=lambda m: m.created_at)

    async def delete_run_messages(self, run_id: str) -> None:
        """删除 Run 消息。"""
        self._messages = [m for m in self._messages if m.run_id != run_id]
