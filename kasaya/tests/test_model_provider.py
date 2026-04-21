"""ModelProvider 单元测试——mock litellm。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kasaya.model._converter import (
    messages_to_litellm,
    model_response_to_assistant_message,
    tool_result_to_message,
    tool_to_openai_schema,
)
from kasaya.model.litellm_provider import LiteLLMProvider
from kasaya.model.message import Message, MessageRole, TokenUsage
from kasaya.model.provider import ModelResponse, ToolCall
from kasaya.model.settings import ModelSettings

# ── 辅助 mock 对象 ──────────────────────────────────────────────


def _make_litellm_response(
    content: str | None = "Hello",
    tool_calls: list[Any] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> MagicMock:
    """构造一个模拟 litellm.acompletion 返回的对象。"""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _make_tool_call_mock(tc_id: str, name: str, arguments: str) -> MagicMock:
    """构造一个模拟 tool_call 对象。"""
    func = MagicMock()
    func.name = name
    func.arguments = arguments

    tc = MagicMock()
    tc.id = tc_id
    tc.function = func
    return tc


# ── 消息转换测试 ────────────────────────────────────────────────


class TestMessagesToLitellm:
    def test_basic_messages(self) -> None:
        msgs = [
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
            Message(role=MessageRole.USER, content="Hi"),
        ]
        result = messages_to_litellm(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "Hi"}

    def test_tool_message_includes_tool_call_id(self) -> None:
        msg = Message(
            role=MessageRole.TOOL,
            content='{"result": 42}',
            tool_call_id="call_abc",
        )
        result = messages_to_litellm([msg])
        assert result[0]["tool_call_id"] == "call_abc"

    def test_assistant_with_tool_calls(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q":"test"}'},
                }
            ],
        )
        result = messages_to_litellm([msg])
        assert result[0]["tool_calls"] is not None
        assert len(result[0]["tool_calls"]) == 1


# ── LiteLLMProvider 非流式测试 ──────────────────────────────────


class TestLiteLLMProviderChat:
    @pytest.mark.asyncio
    async def test_basic_chat(self) -> None:
        mock_resp = _make_litellm_response(content="Hello, world!")
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider()
            result = await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "Hello, world!"
            assert result.finish_reason == "stop"
            assert result.token_usage is not None
            assert result.token_usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self) -> None:
        tc = _make_tool_call_mock("call_1", "search_web", '{"query":"test"}')
        mock_resp = _make_litellm_response(content=None, tool_calls=[tc], finish_reason="tool_calls")

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider()
            result = await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Search for test")],
                tools=[{"type": "function", "function": {"name": "search_web"}}],
            )

            assert isinstance(result, ModelResponse)
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "search_web"
            assert result.tool_calls[0].arguments == '{"query":"test"}'
            assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_chat_with_settings(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider()
            settings = ModelSettings(temperature=0.5, max_tokens=100)
            await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
                settings=settings,
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 100


# ── LiteLLMProvider 流式测试 ────────────────────────────────────


class TestLiteLLMProviderStream:
    @pytest.mark.asyncio
    async def test_stream_basic(self) -> None:
        # 模拟流式 chunk 序列
        chunk1 = MagicMock()
        delta1 = MagicMock()
        delta1.content = "Hello"
        delta1.tool_calls = None
        choice1 = MagicMock()
        choice1.delta = delta1
        choice1.finish_reason = None
        chunk1.choices = [choice1]

        chunk2 = MagicMock()
        delta2 = MagicMock()
        delta2.content = " world"
        delta2.tool_calls = None
        choice2 = MagicMock()
        choice2.delta = delta2
        choice2.finish_reason = "stop"
        chunk2.choices = [choice2]

        async def mock_stream() -> Any:
            for c in [chunk1, chunk2]:
                yield c

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_stream())

            provider = LiteLLMProvider()
            result = await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
                stream=True,
            )

            chunks = []
            async for model_chunk in result:
                chunks.append(model_chunk)

            assert len(chunks) == 2
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " world"
            assert chunks[1].finish_reason == "stop"


# ── 转换工具函数测试 ────────────────────────────────────────────


class TestConverterUtils:
    def test_tool_to_openai_schema(self) -> None:
        schema = tool_to_openai_schema(
            name="search",
            description="Search the web",
            parameters_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "query" in schema["function"]["parameters"]["properties"]

    def test_model_response_to_assistant_message(self) -> None:
        resp = ModelResponse(
            content="Done",
            tool_calls=[],
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )
        msg = model_response_to_assistant_message(resp, agent_name="test-agent")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Done"
        assert msg.agent_name == "test-agent"
        assert msg.token_usage is not None

    def test_model_response_to_assistant_message_with_tool_calls(self) -> None:
        resp = ModelResponse(
            content=None,
            tool_calls=[ToolCall(id="call_1", name="search", arguments='{"q":"x"}')],
            finish_reason="tool_calls",
        )
        msg = model_response_to_assistant_message(resp)
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["function"]["name"] == "search"

    def test_tool_result_to_message(self) -> None:
        msg = tool_result_to_message("call_1", "42", agent_name="calc-agent")
        assert msg.role == MessageRole.TOOL
        assert msg.content == "42"
        assert msg.tool_call_id == "call_1"


# ── LiteLLMProvider 构造参数测试 ──────────────────────────────


class TestLiteLLMProviderInit:
    """验证 LiteLLMProvider api_key/api_base/extra_headers 透传给 litellm。"""

    @pytest.mark.asyncio
    async def test_default_no_extra_params(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider()
            await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert "api_key" not in call_kwargs
            assert "api_base" not in call_kwargs
            assert "extra_headers" not in call_kwargs

    @pytest.mark.asyncio
    async def test_api_key_passed(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider(api_key="sk-test-123")
            await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["api_key"] == "sk-test-123"

    @pytest.mark.asyncio
    async def test_api_base_passed(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider(api_base="https://custom.api.com/v1")
            await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["api_base"] == "https://custom.api.com/v1"

    @pytest.mark.asyncio
    async def test_extra_headers_passed(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider(extra_headers={"X-Custom": "value"})
            await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["extra_headers"] == {"X-Custom": "value"}

    @pytest.mark.asyncio
    async def test_all_params_combined(self) -> None:
        mock_resp = _make_litellm_response()
        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            provider = LiteLLMProvider(
                api_key="sk-combined",
                api_base="https://my-endpoint.com",
                extra_headers={"Authorization": "Bearer xyz"},
            )
            await provider.chat(
                model="deepseek-chat",
                messages=[Message(role=MessageRole.USER, content="Hi")],
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["api_key"] == "sk-combined"
            assert call_kwargs["api_base"] == "https://my-endpoint.com"
            assert call_kwargs["extra_headers"]["Authorization"] == "Bearer xyz"

    @pytest.mark.asyncio
    async def test_stream_passes_provider_params(self) -> None:
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = "Hi"
        delta.tool_calls = None
        choice = MagicMock()
        choice.delta = delta
        choice.finish_reason = "stop"
        chunk.choices = [choice]

        async def mock_stream() -> Any:
            yield chunk

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_stream())

            provider = LiteLLMProvider(api_key="sk-stream", api_base="https://stream.api.com")
            result = await provider.chat(
                model="gpt-4o-mini",
                messages=[Message(role=MessageRole.USER, content="Hi")],
                stream=True,
            )
            async for _ in result:
                pass

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs["api_key"] == "sk-stream"
            assert call_kwargs["api_base"] == "https://stream.api.com"
