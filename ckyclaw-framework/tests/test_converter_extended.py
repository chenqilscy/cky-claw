"""Model converter 扩展测试 — 覆盖 litellm_chunk_to_model_chunk 缺失路径。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from ckyclaw_framework.model._converter import (
    litellm_chunk_to_model_chunk,
    litellm_response_to_model_response,
)


def _make_chunk(*, has_choice: bool = True, content: str | None = None,
                tool_calls: list[Any] | None = None,
                finish_reason: str | None = None) -> MagicMock:
    """创建模拟 litellm 流式 chunk。"""
    chunk = MagicMock()
    if not has_choice:
        chunk.choices = []
        return chunk

    delta = MagicMock()
    delta.content = content
    if tool_calls is not None:
        delta.tool_calls = tool_calls
    else:
        delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    return chunk


class TestLitellmChunkToModelChunk:
    """litellm_chunk_to_model_chunk 测试。"""

    def test_no_choices(self) -> None:
        """无 choices 时返回空 ModelChunk。"""
        chunk = _make_chunk(has_choice=False)
        result = litellm_chunk_to_model_chunk(chunk)
        assert result.content is None
        assert result.tool_call_chunks == []

    def test_content_chunk(self) -> None:
        """有 content 的 chunk。"""
        chunk = _make_chunk(content="Hello")
        result = litellm_chunk_to_model_chunk(chunk)
        assert result.content == "Hello"

    def test_tool_call_chunk(self) -> None:
        """有 tool_calls 的 delta。"""
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_123"
        tc.function = MagicMock()
        tc.function.name = "search"
        tc.function.arguments = '{"query":"test"}'

        chunk = _make_chunk(tool_calls=[tc])
        result = litellm_chunk_to_model_chunk(chunk)
        assert len(result.tool_call_chunks) == 1
        assert result.tool_call_chunks[0].id == "call_123"
        assert result.tool_call_chunks[0].name == "search"
        assert result.tool_call_chunks[0].arguments_delta == '{"query":"test"}'

    def test_tool_call_chunk_no_function(self) -> None:
        """tool_call delta 无 function 时。"""
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_456"
        tc.function = None

        chunk = _make_chunk(tool_calls=[tc])
        result = litellm_chunk_to_model_chunk(chunk)
        assert len(result.tool_call_chunks) == 1
        assert result.tool_call_chunks[0].name is None
        assert result.tool_call_chunks[0].arguments_delta == ""

    def test_finish_reason(self) -> None:
        """finish_reason 被传递。"""
        chunk = _make_chunk(content="", finish_reason="stop")
        result = litellm_chunk_to_model_chunk(chunk)
        assert result.finish_reason == "stop"

    def test_no_tool_calls_on_delta(self) -> None:
        """delta 无 tool_calls 属性时返回空列表。"""
        chunk = _make_chunk(content="text")
        result = litellm_chunk_to_model_chunk(chunk)
        assert result.tool_call_chunks == []


class TestLitellmResponseToModelResponse:
    """litellm_response_to_model_response 补充测试。"""

    def test_no_tool_calls(self) -> None:
        """message 无 tool_calls。"""
        msg = MagicMock()
        msg.content = "Hello"
        msg.tool_calls = None

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"

        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        result = litellm_response_to_model_response(resp)
        assert result.content == "Hello"
        assert result.tool_calls == []
        assert result.token_usage is not None
        assert result.token_usage.total_tokens == 15

    def test_no_usage(self) -> None:
        """无 usage 信息。"""
        msg = MagicMock()
        msg.content = "Hi"
        msg.tool_calls = None

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"

        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = None

        result = litellm_response_to_model_response(resp)
        assert result.token_usage is None

    def test_with_tool_calls(self) -> None:
        """有 tool_calls。"""
        tc = MagicMock()
        tc.id = "call_1"
        tc.function = MagicMock()
        tc.function.name = "calc"
        tc.function.arguments = '{"a": 1}'

        msg = MagicMock()
        msg.content = None
        msg.tool_calls = [tc]

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "tool_calls"

        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)

        result = litellm_response_to_model_response(resp)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "calc"
