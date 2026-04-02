"""内部消息格式转换——CkyClaw Message ↔ LiteLLM/OpenAI 格式。"""

from __future__ import annotations

import json
from typing import Any

from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.model.provider import ModelChunk, ModelResponse, ToolCall, ToolCallChunk


def messages_to_litellm(messages: list[Message]) -> list[dict[str, Any]]:
    """将 CkyClaw Message 列表转换为 LiteLLM/OpenAI 消息格式。"""
    result: list[dict[str, Any]] = []
    for msg in messages:
        entry: dict[str, Any] = {
            "role": msg.role.value,
            "content": msg.content,
        }
        if msg.role == MessageRole.TOOL and msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        result.append(entry)
    return result


def litellm_response_to_model_response(response: Any) -> ModelResponse:
    """将 litellm.acompletion 的响应转为 ModelResponse。"""
    choice = response.choices[0]
    message = choice.message

    # 解析 tool_calls
    tool_calls: list[ToolCall] = []
    if message.tool_calls:
        for tc in message.tool_calls:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                )
            )

    # 解析 token_usage
    token_usage: TokenUsage | None = None
    usage = getattr(response, "usage", None)
    if usage:
        token_usage = TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )

    return ModelResponse(
        content=message.content,
        tool_calls=tool_calls,
        finish_reason=choice.finish_reason,
        token_usage=token_usage,
    )


def litellm_chunk_to_model_chunk(chunk: Any) -> ModelChunk:
    """将 litellm 流式 chunk 转为 ModelChunk。"""
    choice = chunk.choices[0] if chunk.choices else None
    if choice is None:
        return ModelChunk()

    delta = choice.delta

    # 解析增量 tool_calls
    tool_call_chunks: list[ToolCallChunk] = []
    if hasattr(delta, "tool_calls") and delta.tool_calls:
        for tc_delta in delta.tool_calls:
            tool_call_chunks.append(
                ToolCallChunk(
                    index=tc_delta.index,
                    id=getattr(tc_delta, "id", None),
                    name=getattr(tc_delta.function, "name", None) if hasattr(tc_delta, "function") and tc_delta.function else None,
                    arguments_delta=getattr(tc_delta.function, "arguments", "") if hasattr(tc_delta, "function") and tc_delta.function else "",
                )
            )

    return ModelChunk(
        content=getattr(delta, "content", None),
        tool_call_chunks=tool_call_chunks,
        finish_reason=choice.finish_reason,
    )


def tool_to_openai_schema(name: str, description: str, parameters_schema: dict[str, Any]) -> dict[str, Any]:
    """将 FunctionTool 信息转为 OpenAI function calling 格式。"""
    schema: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters_schema or {"type": "object", "properties": {}},
        },
    }
    return schema


def model_response_to_assistant_message(response: ModelResponse, agent_name: str | None = None) -> Message:
    """将 ModelResponse 转为 assistant Message（含 tool_calls 原始格式供历史回放）。"""
    raw_tool_calls: list[dict[str, Any]] | None = None
    if response.tool_calls:
        raw_tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in response.tool_calls
        ]

    return Message(
        role=MessageRole.ASSISTANT,
        content=response.content or "",
        agent_name=agent_name,
        tool_calls=raw_tool_calls,
        token_usage=response.token_usage,
    )


def tool_result_to_message(tool_call_id: str, result: str, agent_name: str | None = None) -> Message:
    """将工具执行结果转为 tool Message。"""
    return Message(
        role=MessageRole.TOOL,
        content=result,
        tool_call_id=tool_call_id,
        agent_name=agent_name,
    )
