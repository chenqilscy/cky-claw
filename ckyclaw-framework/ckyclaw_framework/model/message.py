"""Message / MessageRole / TokenUsage — Agent 通信基本单元。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """消息角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class TokenUsage:
    """Token 消耗统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    """Agent 通信的基本单元。"""

    role: MessageRole
    content: str
    agent_name: str | None = None
    """产生此消息的 Agent（assistant/tool 角色时）"""
    tool_call_id: str | None = None
    """工具调用 ID（tool 角色时）"""
    tool_calls: list[dict[str, Any]] | None = None
    """工具调用请求列表（assistant 角色时）"""
    token_usage: TokenUsage | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        d: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.agent_name is not None:
            d["agent_name"] = self.agent_name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.token_usage is not None:
            d["token_usage"] = {
                "prompt_tokens": self.token_usage.prompt_tokens,
                "completion_tokens": self.token_usage.completion_tokens,
                "total_tokens": self.token_usage.total_tokens,
            }
        d["timestamp"] = self.timestamp.isoformat()
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """从字典反序列化。"""
        token_usage = None
        if data.get("token_usage"):
            tu = data["token_usage"]
            token_usage = TokenUsage(
                prompt_tokens=tu.get("prompt_tokens", 0),
                completion_tokens=tu.get("completion_tokens", 0),
                total_tokens=tu.get("total_tokens", 0),
            )
        timestamp = (
            datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc)
        )
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            agent_name=data.get("agent_name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            token_usage=token_usage,
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )
