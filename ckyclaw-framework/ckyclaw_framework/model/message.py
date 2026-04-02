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
