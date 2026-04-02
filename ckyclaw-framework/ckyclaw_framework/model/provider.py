"""ModelProvider — LLM 模型提供商抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message
    from ckyclaw_framework.model.settings import ModelSettings


@dataclass
class ModelResponse:
    """LLM 响应。"""

    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class ModelChunk:
    """LLM 流式响应片段。"""

    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None


class ModelProvider(ABC):
    """LLM 模型提供商抽象。"""

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        """发送聊天请求。"""
        ...
