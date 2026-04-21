"""ModelProvider — LLM 模型提供商抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from kasaya.model.message import Message, TokenUsage
    from kasaya.model.settings import ModelSettings


@dataclass
class ToolCall:
    """LLM 返回的工具调用请求。"""

    id: str
    """工具调用唯一标识（由 LLM 生成）"""

    name: str
    """工具名称"""

    arguments: str
    """JSON 字符串形式的参数"""


@dataclass
class ToolCallChunk:
    """流式模式下的工具调用增量片段。"""

    index: int
    """tool_calls 数组中的索引"""

    id: str | None = None
    """首个 chunk 携带 id"""

    name: str | None = None
    """首个 chunk 携带 name"""

    arguments_delta: str = ""
    """arguments 的增量片段"""


@dataclass
class ModelResponse:
    """LLM 完整响应。"""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    token_usage: TokenUsage | None = None


@dataclass
class ModelChunk:
    """LLM 流式响应片段。"""

    content: str | None = None
    tool_call_chunks: list[ToolCallChunk] = field(default_factory=list)
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
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        """发送聊天请求。

        Args:
            response_format: 结构化输出格式（如 {"type": "json_object"} 或 JSON Schema）。
        """
        ...
