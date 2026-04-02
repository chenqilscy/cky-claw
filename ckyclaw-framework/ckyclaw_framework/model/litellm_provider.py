"""LiteLLMProvider — 基于 LiteLLM 的多模型适配实现。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message
    from ckyclaw_framework.model.settings import ModelSettings


class LiteLLMProvider(ModelProvider):
    """基于 LiteLLM 的多模型适配实现。支持 100+ 模型。"""

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        """通过 litellm.acompletion 调用。"""
        raise NotImplementedError
