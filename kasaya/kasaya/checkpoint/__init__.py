"""Checkpoint — Agent 运行循环中间状态快照与恢复。

在 Runner 执行过程中定期保存 checkpoint，支持进程崩溃后从最近 checkpoint 恢复，
避免 Token 浪费和重复执行。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from kasaya.model.message import Message


@dataclass
class Checkpoint:
    """Agent 运行循环的中间状态快照。"""

    checkpoint_id: str = field(default_factory=lambda: uuid4().hex)
    """唯一标识"""

    run_id: str = ""
    """所属运行 ID"""

    turn_count: int = 0
    """当前回合数"""

    current_agent_name: str = ""
    """当前正在执行的 Agent 名称"""

    messages: list[Message] = field(default_factory=list)
    """完整的消息历史"""

    token_usage: dict[str, int] = field(default_factory=dict)
    """累计 Token 用量"""

    context: dict[str, Any] = field(default_factory=dict)
    """用户自定义上下文"""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """创建时间"""

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """从字典反序列化。"""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            data = {**data, "created_at": datetime.fromisoformat(created_at)}
        # 过滤未知字段（向后兼容保护）
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class CheckpointBackend(ABC):
    """Checkpoint 存储后端抽象接口。"""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None:
        """保存 checkpoint。"""

    @abstractmethod
    async def load_latest(self, run_id: str) -> Checkpoint | None:
        """加载指定 run_id 的最新 checkpoint。"""

    @abstractmethod
    async def list_checkpoints(self, run_id: str) -> list[Checkpoint]:
        """列出指定 run_id 的所有 checkpoint（按 turn_count 升序）。"""

    @abstractmethod
    async def delete(self, run_id: str) -> None:
        """删除指定 run_id 的全部 checkpoint。"""


class InMemoryCheckpointBackend(CheckpointBackend):
    """基于内存的 Checkpoint 后端（测试/开发用）。"""

    def __init__(self) -> None:
        self._store: dict[str, list[Checkpoint]] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        """保存 checkpoint 到内存。"""
        if checkpoint.run_id not in self._store:
            self._store[checkpoint.run_id] = []
        self._store[checkpoint.run_id].append(checkpoint)

    async def load_latest(self, run_id: str) -> Checkpoint | None:
        """加载最新 checkpoint。"""
        checkpoints = self._store.get(run_id, [])
        if not checkpoints:
            return None
        return max(checkpoints, key=lambda c: c.turn_count)

    async def list_checkpoints(self, run_id: str) -> list[Checkpoint]:
        """列出所有 checkpoint（按 turn_count 升序）。"""
        checkpoints = self._store.get(run_id, [])
        return sorted(checkpoints, key=lambda c: c.turn_count)

    async def delete(self, run_id: str) -> None:
        """删除全部 checkpoint。"""
        self._store.pop(run_id, None)
