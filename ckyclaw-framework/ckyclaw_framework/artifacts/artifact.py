"""Artifact 数据类 — 外部化的大型工具输出。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class Artifact:
    """外部化的大型工具输出。

    当工具返回结果超过 token 阈值时，Runner 将结果存入 ArtifactStore，
    上下文中只保留摘要 + artifact_id 引用。
    """

    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    """全局唯一标识"""

    run_id: str = ""
    """所属运行 ID"""

    content: str = ""
    """原始完整内容"""

    summary: str = ""
    """摘要（截取前 max_summary_chars 字符 + 省略标记）"""

    token_count: int = 0
    """估算的 token 数"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """扩展元数据（tool_name, tool_call_id 等）"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict。"""
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "content": self.content,
            "summary": self.summary,
            "token_count": self.token_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        """从 dict 反序列化。"""
        created_at_raw = data.get("created_at")
        if isinstance(created_at_raw, str):
            created_at = datetime.fromisoformat(created_at_raw)
        elif isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        else:
            created_at = datetime.now(timezone.utc)
        return cls(
            artifact_id=data.get("artifact_id", uuid.uuid4().hex),
            run_id=data.get("run_id", ""),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            token_count=data.get("token_count", 0),
            metadata=data.get("metadata", {}),
            created_at=created_at,
        )
