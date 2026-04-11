"""Memory — 跨会话长期记忆核心类型与抽象后端。"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class MemoryType(str, Enum):
    """记忆条目类型。"""

    USER_PROFILE = "user_profile"
    """用户档案 — 偏好、习惯、技术栈、身份信息。"""

    HISTORY_SUMMARY = "history_summary"
    """历史摘要 — 长对话自动生成的压缩摘要。"""

    STRUCTURED_FACT = "structured_fact"
    """结构化事实 — Agent 执行中积累的事实数据。"""


class DecayMode(str, Enum):
    """记忆衰减模式。"""

    LINEAR = "linear"
    """线性衰减: new_confidence = max(0.0, confidence - rate)"""

    EXPONENTIAL = "exponential"
    """指数衰减（艾宾浩斯遗忘曲线）: new_confidence = confidence × e^(-λ × days)"""


@dataclass
class MemoryEntry:
    """记忆条目。"""

    id: str = field(default_factory=lambda: str(uuid4()))
    """条目唯一标识。"""

    type: MemoryType = MemoryType.STRUCTURED_FACT
    """条目类型。"""

    content: str = ""
    """记忆内容文本。"""

    confidence: float = 1.0
    """置信度分数（0.0 ~ 1.0）。越高表示越可靠。"""

    user_id: str = ""
    """所属用户标识。"""

    agent_name: str | None = None
    """产生此记忆的 Agent 名称。"""

    source_session_id: str | None = None
    """来源会话 ID。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """创建时间。"""

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """最后更新时间。"""

    embedding: list[float] | None = None
    """可选向量表示，用于语义相似度检索。"""

    tags: list[str] = field(default_factory=list)
    """分类标签，用于快速过滤和分组检索。"""

    access_count: int = 0
    """访问计数，用于热度排序和 LRU 淘汰。"""


class MemoryBackend(ABC):
    """记忆存储后端抽象。

    所有方法都以 user_id 为必需参数，强制用户隔离。
    """

    @abstractmethod
    async def store(self, user_id: str, entry: MemoryEntry) -> None:
        """存储或更新一条记忆条目。

        若 entry.id 已存在，执行更新（upsert 语义）。
        """
        ...

    @abstractmethod
    async def search(
        self, user_id: str, query: str, *, limit: int = 10
    ) -> list[MemoryEntry]:
        """按关键词搜索用户的记忆条目。

        Args:
            user_id: 用户标识。
            query: 搜索关键词。
            limit: 返回条目上限。

        Returns:
            按相关性排序的记忆条目列表。
        """
        ...

    @abstractmethod
    async def list_entries(
        self,
        user_id: str,
        *,
        memory_type: MemoryType | None = None,
        agent_name: str | None = None,
    ) -> list[MemoryEntry]:
        """列出用户的记忆条目。

        Args:
            user_id: 用户标识。
            memory_type: 按类型过滤。
            agent_name: 按 Agent 名称过滤。
        """
        ...

    @abstractmethod
    async def get(self, entry_id: str) -> MemoryEntry | None:
        """获取单条记忆条目。"""
        ...

    @abstractmethod
    async def delete(self, entry_id: str) -> None:
        """删除一条记忆条目。"""
        ...

    @abstractmethod
    async def delete_by_user(self, user_id: str) -> int:
        """删除指定用户的全部记忆。

        Returns:
            删除的条目数量。
        """
        ...

    @abstractmethod
    async def decay(
        self,
        before: datetime,
        rate: float,
        *,
        mode: DecayMode = DecayMode.LINEAR,
    ) -> int:
        """对 updated_at < before 的条目降低 confidence。

        Args:
            before: 时间阈值，仅影响此时间之前的条目。
            rate: 衰减参数——
                LINEAR 模式: 每次降低的固定值（如 0.05）。
                EXPONENTIAL 模式: λ 衰减系数（如 0.1），天数越大衰减越多。
            mode: 衰减模式，默认 LINEAR。

        Returns:
            受影响的条目数量。
        """
        ...

    async def count(self, user_id: str) -> int:
        """返回用户记忆条目总数。

        默认实现通过 list_entries 计算。子类可覆盖为更高效实现。
        """
        entries = await self.list_entries(user_id)
        return len(entries)

    async def search_by_tags(
        self,
        user_id: str,
        tags: list[str],
        *,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """按标签搜索用户记忆条目。

        默认实现在 list_entries 结果中过滤。子类可覆盖为索引级查询。

        Args:
            user_id: 用户标识。
            tags: 标签列表（OR 匹配：条目含任一标签即命中）。
            limit: 返回条目上限。
        """
        entries = await self.list_entries(user_id)
        tag_set = set(tags)
        matched = [e for e in entries if tag_set & set(e.tags)]
        matched.sort(key=lambda e: (-e.confidence, -e.updated_at.timestamp()))
        return matched[:limit]


def compute_exponential_decay(
    confidence: float,
    days_since_update: float,
    lambda_: float,
) -> float:
    """计算指数衰减后的置信度（艾宾浩斯遗忘曲线）。

    公式: new_confidence = confidence × e^(-λ × days)

    Args:
        confidence: 原始置信度。
        days_since_update: 距离最后更新的天数。
        lambda_: 衰减速率系数（越大衰减越快，推荐 0.05~0.3）。

    Returns:
        衰减后的置信度，最小为 0.0。
    """
    if days_since_update <= 0 or lambda_ <= 0:
        return confidence
    return max(0.0, confidence * math.exp(-lambda_ * days_since_update))
