"""A2A Task — 任务生命周期管理。

遵循 Google A2A 协议 Task 生命周期：
submitted → working → completed / failed / canceled

每个 Task 附带输入消息、输出产物和状态变迁历史。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """A2A 任务状态。"""

    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class TaskState:
    """任务状态变迁记录。"""

    status: TaskStatus
    """状态。"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """变迁时间。"""

    message: str = ""
    """状态说明。"""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


@dataclass
class TaskArtifact:
    """任务产出物。"""

    name: str
    """产出物名称。"""

    parts: list[dict[str, Any]] = field(default_factory=list)
    """产出物内容部分（支持多种 MIME 类型）。

    每个 part 示例: {"type": "text/plain", "text": "..."} 或
    {"type": "image/png", "data": "<base64>"}
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据。"""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "name": self.name,
            "parts": self.parts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskArtifact:
        """从字典反序列化。"""
        return cls(
            name=data["name"],
            parts=data.get("parts", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class A2ATask:
    """A2A 任务 — 跨 Agent 交互的基本单元。

    使用示例::

        task = A2ATask(
            input_messages=[{"role": "user", "parts": [{"type": "text/plain", "text": "审查这段代码"}]}],
        )
        task.transition(TaskStatus.WORKING, "开始处理")
        # ... Agent 执行逻辑 ...
        task.add_artifact(TaskArtifact(name="review", parts=[{"type": "text/plain", "text": "审查结论"}]))
        task.transition(TaskStatus.COMPLETED, "审查完成")
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """任务唯一标识。"""

    status: TaskStatus = TaskStatus.SUBMITTED
    """当前状态。"""

    input_messages: list[dict[str, Any]] = field(default_factory=list)
    """输入消息列表（遵循 A2A Message 格式）。"""

    artifacts: list[TaskArtifact] = field(default_factory=list)
    """产出物列表。"""

    history: list[TaskState] = field(default_factory=list)
    """状态变迁历史。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据（如调用方 Agent 信息）。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """创建时间。"""

    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """最后更新时间。"""

    def __post_init__(self) -> None:
        """初始化后记录初始状态。"""
        if not self.history:
            self.history.append(TaskState(status=self.status, message="任务创建"))

    def transition(self, new_status: TaskStatus, message: str = "") -> None:
        """状态变迁。

        Args:
            new_status: 目标状态。
            message: 变迁说明。

        Raises:
            ValueError: 非法状态变迁。
        """
        valid_transitions: dict[TaskStatus, set[TaskStatus]] = {
            TaskStatus.SUBMITTED: {TaskStatus.WORKING, TaskStatus.CANCELED},
            TaskStatus.WORKING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED},
        }
        allowed = valid_transitions.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"非法状态变迁: {self.status.value} → {new_status.value}，"
                f"允许的目标: {[s.value for s in allowed]}"
            )
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        self.history.append(TaskState(status=new_status, message=message))

    def add_artifact(self, artifact: TaskArtifact) -> None:
        """添加产出物。"""
        self.artifacts.append(artifact)
        self.updated_at = datetime.now(UTC)

    @property
    def is_terminal(self) -> bool:
        """是否处于终态。"""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED}

    def to_dict(self) -> dict[str, Any]:
        """序列化为 A2A 规范字典。"""
        return {
            "id": self.id,
            "status": self.status.value,
            "inputMessages": self.input_messages,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "history": [h.to_dict() for h in self.history],
            "metadata": self.metadata,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2ATask:
        """从字典反序列化。"""
        task = cls(
            id=data["id"],
            status=TaskStatus(data["status"]),
            input_messages=data.get("inputMessages", []),
            artifacts=[TaskArtifact.from_dict(a) for a in data.get("artifacts", [])],
            metadata=data.get("metadata", {}),
        )
        # 替换历史
        task.history = [
            TaskState(
                status=TaskStatus(h["status"]),
                timestamp=datetime.fromisoformat(h["timestamp"]),
                message=h.get("message", ""),
            )
            for h in data.get("history", [])
        ]
        return task
