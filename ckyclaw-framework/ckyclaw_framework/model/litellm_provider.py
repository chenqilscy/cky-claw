"""LiteLLMProvider — 基于 LiteLLM 的多模型适配实现。"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import litellm

from ckyclaw_framework.model._converter import (
    litellm_chunk_to_model_chunk,
    litellm_response_to_model_response,
    messages_to_litellm,
)
from ckyclaw_framework.model.message import Message
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse
from ckyclaw_framework.model.settings import ModelSettings

logger = logging.getLogger(__name__)


class LiteLLMProvider(ModelProvider):
    """基于 LiteLLM 的多模型适配实现。支持 100+ 模型。

    Args:
        api_key: API 密钥。不传则使用环境变量。
        api_base: API 端点 URL。不传则使用 LiteLLM 默认值。
        extra_headers: 额外请求头（如自定义认证头）。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._extra_headers = extra_headers

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
        """通过 litellm.acompletion 调用。"""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages_to_litellm(messages),
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        # Provider 级别参数
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if self._api_base is not None:
            kwargs["api_base"] = self._api_base
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers

        if tools:
            kwargs["tools"] = tools

        if settings:
            if settings.temperature is not None:
                kwargs["temperature"] = settings.temperature
            if settings.max_tokens is not None:
                kwargs["max_tokens"] = settings.max_tokens
            if settings.top_p is not None:
                kwargs["top_p"] = settings.top_p
            if settings.stop is not None:
                kwargs["stop"] = settings.stop
            if settings.extra:
                kwargs.update(settings.extra)

        if stream:
            return self._stream(kwargs)

        response = await litellm.acompletion(**kwargs)
        return litellm_response_to_model_response(response)

    async def _stream(self, kwargs: dict[str, Any]) -> AsyncIterator[ModelChunk]:
        """内部流式调用——返回 ModelChunk 异步迭代器。"""
        kwargs["stream"] = True
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            yield litellm_chunk_to_model_chunk(chunk)
