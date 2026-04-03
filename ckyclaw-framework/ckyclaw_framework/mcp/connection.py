"""MCP 连接管理 — 封装 stdio / sse / http 三种传输的连接与工具发现。"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from contextlib import AsyncExitStack
from typing import Any

from ckyclaw_framework.mcp.server import MCPServerConfig
from ckyclaw_framework.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)


def _ensure_mcp_installed() -> None:
    """检查 mcp SDK 是否已安装。"""
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "MCP SDK 未安装。请运行: pip install 'ckyclaw-framework[mcp]' 或 pip install mcp"
        ) from exc


def _create_mcp_tool(
    session: Any,
    server_name: str,
    tool_info: Any,
    timeout: float,
) -> FunctionTool:
    """将 MCP 工具 schema 包装为 FunctionTool。

    工具名称添加 namespace 前缀: ``{server_name}::{tool_name}``
    """
    raw_name: str = tool_info.name
    namespaced_name = f"{server_name}::{raw_name}"
    description = tool_info.description or ""
    input_schema: dict[str, Any] = {}
    if hasattr(tool_info, "inputSchema") and tool_info.inputSchema:
        input_schema = dict(tool_info.inputSchema)

    async def _call_mcp_tool(**kwargs: Any) -> str:
        """通过 MCP 协议调用远程工具。"""
        from mcp import types

        result = await asyncio.wait_for(
            session.call_tool(raw_name, arguments=kwargs),
            timeout=timeout,
        )
        # 拼接所有 TextContent
        parts: list[str] = []
        if result.content:
            for content in result.content:
                if isinstance(content, types.TextContent):
                    parts.append(content.text)
                elif isinstance(content, types.ImageContent):
                    parts.append(f"[image: {content.mimeType}]")
                elif isinstance(content, types.EmbeddedResource):
                    resource = content.resource
                    if hasattr(resource, "text"):
                        parts.append(resource.text)
                    else:
                        parts.append(f"[resource: {resource.uri}]")
                else:
                    parts.append(str(content))
        if result.isError:
            return f"Error: {' '.join(parts) or 'MCP tool returned error'}"
        return "\n".join(parts) if parts else ""

    return FunctionTool(
        name=namespaced_name,
        description=f"[MCP:{server_name}] {description}",
        fn=_call_mcp_tool,
        parameters_schema=input_schema,
        timeout=None,  # 超时由 _call_mcp_tool 内部控制
    )


async def connect_and_discover(
    stack: AsyncExitStack,
    config: MCPServerConfig,
) -> list[FunctionTool]:
    """连接 MCP Server 并发现工具。

    Args:
        stack: 异步退出栈，用于管理连接生命周期。
        config: MCP Server 配置。

    Returns:
        该 Server 提供的工具列表（已封装为 FunctionTool）。
    """
    _ensure_mcp_installed()

    from mcp import ClientSession

    if config.transport == "stdio":
        tools = await _connect_stdio(stack, config)
    elif config.transport == "sse":
        tools = await _connect_sse(stack, config)
    elif config.transport == "http":
        tools = await _connect_http(stack, config)
    else:
        logger.error("不支持的 MCP 传输类型: %s", config.transport)
        return []

    return tools


async def _connect_stdio(
    stack: AsyncExitStack,
    config: MCPServerConfig,
) -> list[FunctionTool]:
    """通过 stdio 传输连接 MCP Server。"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not config.command:
        logger.error("MCP Server '%s' stdio 模式缺少 command 配置", config.name)
        return []

    # 解析命令行: "npx -y @mcp/server-fs /data" → command="npx", args=["-y", "@mcp/server-fs", "/data"]
    parts = shlex.split(config.command)
    command = parts[0]
    args = parts[1:] + config.args

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=config.env or None,
    )

    try:
        transport = await asyncio.wait_for(
            stack.enter_async_context(stdio_client(server_params)),
            timeout=config.connect_timeout,
        )
        read_stream, write_stream = transport
        session: ClientSession = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await asyncio.wait_for(session.initialize(), timeout=config.connect_timeout)
        return await _discover_tools(session, config)
    except asyncio.TimeoutError:
        logger.error("MCP Server '%s' stdio 连接超时（%ss）", config.name, config.connect_timeout)
        return []
    except Exception:
        logger.exception("MCP Server '%s' stdio 连接失败", config.name)
        return []


async def _connect_sse(
    stack: AsyncExitStack,
    config: MCPServerConfig,
) -> list[FunctionTool]:
    """通过 SSE 传输连接 MCP Server。"""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    if not config.url:
        logger.error("MCP Server '%s' sse 模式缺少 url 配置", config.name)
        return []

    try:
        transport = await asyncio.wait_for(
            stack.enter_async_context(sse_client(config.url, headers=config.headers or None)),
            timeout=config.connect_timeout,
        )
        read_stream, write_stream = transport
        session: ClientSession = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await asyncio.wait_for(session.initialize(), timeout=config.connect_timeout)
        return await _discover_tools(session, config)
    except asyncio.TimeoutError:
        logger.error("MCP Server '%s' sse 连接超时（%ss）", config.name, config.connect_timeout)
        return []
    except Exception:
        logger.exception("MCP Server '%s' sse 连接失败", config.name)
        return []


async def _connect_http(
    stack: AsyncExitStack,
    config: MCPServerConfig,
) -> list[FunctionTool]:
    """通过 Streamable HTTP 传输连接 MCP Server。"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    if not config.url:
        logger.error("MCP Server '%s' http 模式缺少 url 配置", config.name)
        return []

    try:
        transport = await asyncio.wait_for(
            stack.enter_async_context(streamable_http_client(config.url, headers=config.headers or None)),
            timeout=config.connect_timeout,
        )
        read_stream, write_stream = transport[0], transport[1]
        session: ClientSession = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await asyncio.wait_for(session.initialize(), timeout=config.connect_timeout)
        return await _discover_tools(session, config)
    except asyncio.TimeoutError:
        logger.error("MCP Server '%s' http 连接超时（%ss）", config.name, config.connect_timeout)
        return []
    except Exception:
        logger.exception("MCP Server '%s' http 连接失败", config.name)
        return []


async def _discover_tools(
    session: Any,
    config: MCPServerConfig,
) -> list[FunctionTool]:
    """从 MCP Session 发现并封装工具。"""
    try:
        tools_response = await asyncio.wait_for(
            session.list_tools(),
            timeout=config.connect_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("MCP Server '%s' list_tools 超时", config.name)
        return []
    except Exception:
        logger.exception("MCP Server '%s' list_tools 失败", config.name)
        return []

    tools: list[FunctionTool] = []
    for tool_info in tools_response.tools:
        ft = _create_mcp_tool(session, config.name, tool_info, config.tool_call_timeout)
        tools.append(ft)
        logger.debug(
            "MCP Server '%s' 注册工具: %s (%s)",
            config.name,
            ft.name,
            tool_info.description or "无描述",
        )

    logger.info("MCP Server '%s' 发现 %d 个工具", config.name, len(tools))
    return tools
