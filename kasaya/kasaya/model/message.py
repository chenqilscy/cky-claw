"""Message / MessageRole / TokenUsage — Agent 通信基本单元。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from kasaya.model.content_block import (
    ContentBlock,
    content_block_from_dict,
    content_blocks_to_text,
)


class MessageRole(StrEnum):
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
    """Agent 通信的基本单元。

    content 用于纯文本场景（向后兼容），content_blocks 用于多模态场景。
    两者只需提供一个；同时提供时 content_blocks 优先。
    """

    role: MessageRole
    content: str
    content_blocks: list[ContentBlock] | None = None
    """多模态内容块列表。提供时 content 作为纯文本降级表示。"""
    agent_name: str | None = None
    """产生此消息的 Agent（assistant/tool 角色时）"""
    tool_call_id: str | None = None
    """工具调用 ID（tool 角色时）"""
    tool_calls: list[dict[str, Any]] | None = None
    """工具调用请求列表（assistant 角色时）"""
    token_usage: TokenUsage | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text_content(self) -> str:
        """获取纯文本内容——优先从 content_blocks 提取。"""
        if self.content_blocks:
            return content_blocks_to_text(self.content_blocks)
        return self.content

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        d: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.content_blocks is not None:
            d["content_blocks"] = [b.to_dict() for b in self.content_blocks]
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
            else datetime.now(UTC)
        )
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            content_blocks=[
                content_block_from_dict(b) for b in data["content_blocks"]
            ] if data.get("content_blocks") else None,
            agent_name=data.get("agent_name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            token_usage=token_usage,
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )
