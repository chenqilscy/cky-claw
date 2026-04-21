"""MCP SDK 集成测试 — Framework MCP 模块。"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types as mcp_types

from kasaya.mcp.connection import (
    _create_mcp_tool,
    _discover_tools,
    _ensure_mcp_installed,
    connect_and_discover,
)
from kasaya.mcp.server import MCPServerConfig
from kasaya.tools.function_tool import FunctionTool

# ---------------------------------------------------------------------------
# MCPServerConfig 数据类测试
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    def test_defaults(self) -> None:
        config = MCPServerConfig(name="test", transport="stdio")
        assert config.name == "test"
        assert config.transport == "stdio"
        assert config.command is None
        assert config.url is None
        assert config.args == []
        assert config.env == {}
        assert config.headers == {}
        assert config.connect_timeout == 30.0
        assert config.tool_call_timeout == 60.0

    def test_stdio_config(self) -> None:
        config = MCPServerConfig(
            name="fs-server",
            transport="stdio",
            command="npx -y @mcp/server-fs /data",
            env={"NODE_ENV": "production"},
        )
        assert config.command == "npx -y @mcp/server-fs /data"
        assert config.env["NODE_ENV"] == "production"

    def test_sse_config(self) -> None:
        config = MCPServerConfig(
            name="remote-mcp",
            transport="sse",
            url="https://mcp.example.com/sse",
            headers={"Authorization": "Bearer xxx"},
        )
        assert config.url == "https://mcp.example.com/sse"
        assert config.headers["Authorization"] == "Bearer xxx"

    def test_http_config(self) -> None:
        config = MCPServerConfig(
            name="http-mcp",
            transport="http",
            url="http://localhost:8080/mcp",
        )
        assert config.transport == "http"

    def test_custom_timeouts(self) -> None:
        config = MCPServerConfig(
            name="slow",
            transport="stdio",
            connect_timeout=60.0,
            tool_call_timeout=120.0,
        )
        assert config.connect_timeout == 60.0
        assert config.tool_call_timeout == 120.0


# ---------------------------------------------------------------------------
# _ensure_mcp_installed 测试
# ---------------------------------------------------------------------------


class TestEnsureMCPInstalled:
    def test_mcp_installed(self) -> None:
        _ensure_mcp_installed()

    def test_mcp_not_installed(self) -> None:
        with patch.dict("sys.modules", {"mcp": None}), pytest.raises(ImportError, match="MCP SDK 未安装"):
            _ensure_mcp_installed()


# ---------------------------------------------------------------------------
# _create_mcp_tool 测试
# ---------------------------------------------------------------------------


class TestCreateMCPTool:
    def test_tool_namespace_and_description(self) -> None:
        session = MagicMock()
        tool_info = MagicMock()
        tool_info.name = "list_files"
        tool_info.description = "List files in a directory"
        tool_info.inputSchema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

        tool = _create_mcp_tool(session, "fs-server", tool_info, timeout=30.0)

        assert isinstance(tool, FunctionTool)
        assert tool.name == "fs-server::list_files"
        assert "[MCP:fs-server]" in tool.description
        assert "List files in a directory" in tool.description
        assert tool.parameters_schema["type"] == "object"
        assert "path" in tool.parameters_schema["properties"]

    def test_tool_no_description_no_schema(self) -> None:
        session = MagicMock()
        tool_info = MagicMock()
        tool_info.name = "do_thing"
        tool_info.description = None
        tool_info.inputSchema = None

        tool = _create_mcp_tool(session, "test", tool_info, timeout=10.0)

        assert tool.name == "test::do_thing"
        assert "[MCP:test]" in tool.description
        assert tool.parameters_schema == {}

    @pytest.mark.asyncio
    async def test_tool_calls_session_call_tool(self) -> None:
        """验证工具调用正确转发到 session.call_tool。"""
        text_content = mcp_types.TextContent(type="text", text="42")
        mock_result = MagicMock()
        mock_result.content = [text_content]
        mock_result.isError = False

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        tool_info = MagicMock()
        tool_info.name = "add"
        tool_info.description = "Add numbers"
        tool_info.inputSchema = {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        }

        tool = _create_mcp_tool(session, "calc", tool_info, timeout=10.0)
        result = await tool.execute({"a": 1, "b": 2})

        assert "42" in result
        session.call_tool.assert_awaited_once_with("add", arguments={"a": 1, "b": 2})

    @pytest.mark.asyncio
    async def test_tool_error_result(self) -> None:
        """MCP 工具返回 isError=True 时前缀 'Error:'。"""
        text_content = mcp_types.TextContent(type="text", text="division by zero")
        mock_result = MagicMock()
        mock_result.content = [text_content]
        mock_result.isError = True

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        tool_info = MagicMock()
        tool_info.name = "divide"
        tool_info.description = "Divide"
        tool_info.inputSchema = {"type": "object", "properties": {}}

        tool = _create_mcp_tool(session, "calc", tool_info, timeout=10.0)
        result = await tool.execute({})

        assert result.startswith("Error:")
        assert "division by zero" in result

    @pytest.mark.asyncio
    async def test_tool_timeout(self) -> None:
        """工具调用超时返回错误信息。"""

        async def slow_call(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(10)

        session = MagicMock()
        session.call_tool = slow_call

        tool_info = MagicMock()
        tool_info.name = "slow"
        tool_info.description = "Slow tool"
        tool_info.inputSchema = {"type": "object", "properties": {}}

        tool = _create_mcp_tool(session, "test", tool_info, timeout=0.05)
        result = await tool.execute({})

        assert "timed out" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_tool_image_content(self) -> None:
        """ImageContent 转为 [image: mime] 标记。"""
        img_content = mcp_types.ImageContent(type="image", data="base64...", mimeType="image/png")
        mock_result = MagicMock()
        mock_result.content = [img_content]
        mock_result.isError = False

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        tool_info = MagicMock()
        tool_info.name = "screenshot"
        tool_info.description = "Take screenshot"
        tool_info.inputSchema = {"type": "object", "properties": {}}

        tool = _create_mcp_tool(session, "test", tool_info, timeout=10.0)
        result = await tool.execute({})

        assert "[image: image/png]" in result

    @pytest.mark.asyncio
    async def test_tool_empty_result(self) -> None:
        """MCP 工具返回空内容时返回空字符串。"""
        mock_result = MagicMock()
        mock_result.content = []
        mock_result.isError = False

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        tool_info = MagicMock()
        tool_info.name = "noop"
        tool_info.description = "No-op"
        tool_info.inputSchema = {"type": "object", "properties": {}}

        tool = _create_mcp_tool(session, "test", tool_info, timeout=10.0)
        result = await tool.execute({})

        assert result == ""

    @pytest.mark.asyncio
    async def test_tool_multiple_text_content(self) -> None:
        """多个 TextContent 以换行拼接。"""
        c1 = mcp_types.TextContent(type="text", text="line1")
        c2 = mcp_types.TextContent(type="text", text="line2")
        mock_result = MagicMock()
        mock_result.content = [c1, c2]
        mock_result.isError = False

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=mock_result)

        tool_info = MagicMock()
        tool_info.name = "multi"
        tool_info.description = "Multi"
        tool_info.inputSchema = {"type": "object", "properties": {}}

        tool = _create_mcp_tool(session, "test", tool_info, timeout=10.0)
        result = await tool.execute({})

        assert result == "line1\nline2"


# ---------------------------------------------------------------------------
# _discover_tools 测试
# ---------------------------------------------------------------------------


class TestDiscoverTools:
    @pytest.mark.asyncio
    async def test_discover_tools_normal(self) -> None:
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool_a"
        mock_tool1.description = "Tool A"
        mock_tool1.inputSchema = {"type": "object", "properties": {}}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool_b"
        mock_tool2.description = "Tool B"
        mock_tool2.inputSchema = {"type": "object", "properties": {"x": {"type": "string"}}}

        mock_response = MagicMock()
        mock_response.tools = [mock_tool1, mock_tool2]

        session = MagicMock()
        session.list_tools = AsyncMock(return_value=mock_response)

        config = MCPServerConfig(name="test-server", transport="stdio")
        tools = await _discover_tools(session, config)

        assert len(tools) == 2
        assert tools[0].name == "test-server::tool_a"
        assert tools[1].name == "test-server::tool_b"
        assert all(isinstance(t, FunctionTool) for t in tools)

    @pytest.mark.asyncio
    async def test_discover_tools_empty_list(self) -> None:
        mock_response = MagicMock()
        mock_response.tools = []

        session = MagicMock()
        session.list_tools = AsyncMock(return_value=mock_response)

        config = MCPServerConfig(name="empty", transport="stdio")
        tools = await _discover_tools(session, config)

        assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_timeout(self) -> None:
        async def slow_list() -> None:
            await asyncio.sleep(10)

        session = MagicMock()
        session.list_tools = slow_list

        config = MCPServerConfig(name="test", transport="stdio", connect_timeout=0.05)
        tools = await _discover_tools(session, config)

        assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_exception(self) -> None:
        session = MagicMock()
        session.list_tools = AsyncMock(side_effect=RuntimeError("connection lost"))

        config = MCPServerConfig(name="test", transport="stdio")
        tools = await _discover_tools(session, config)

        assert tools == []


# ---------------------------------------------------------------------------
# connect_and_discover 测试
# ---------------------------------------------------------------------------


def _make_mock_stdio_context(mock_session: MagicMock) -> tuple[MagicMock, MagicMock]:
    """构建 stdio_client 和 ClientSession mock。"""
    mock_transport = (MagicMock(), MagicMock())
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_session


class TestConnectAndDiscover:
    @pytest.mark.asyncio
    async def test_unsupported_transport(self) -> None:
        config = MCPServerConfig(name="bad", transport="websocket")
        stack = AsyncExitStack()
        async with stack:
            tools = await connect_and_discover(stack, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_stdio_missing_command(self) -> None:
        config = MCPServerConfig(name="no-cmd", transport="stdio", command=None)
        stack = AsyncExitStack()
        async with stack:
            tools = await connect_and_discover(stack, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_sse_missing_url(self) -> None:
        config = MCPServerConfig(name="no-url", transport="sse", url=None)
        stack = AsyncExitStack()
        async with stack:
            tools = await connect_and_discover(stack, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_http_missing_url(self) -> None:
        config = MCPServerConfig(name="no-url", transport="http", url=None)
        stack = AsyncExitStack()
        async with stack:
            tools = await connect_and_discover(stack, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_stdio_connect_success(self) -> None:
        """验证 stdio 连接流程（全 mock）。"""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        mock_response = MagicMock()
        mock_response.tools = [mock_tool]

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_response)
        mock_ctx, mock_session = _make_mock_stdio_context(mock_session)

        with (
            patch("mcp.client.stdio.stdio_client", return_value=mock_ctx),
            patch("mcp.ClientSession", return_value=mock_session),
        ):
            config = MCPServerConfig(name="test-fs", transport="stdio", command="npx server-fs")
            stack = AsyncExitStack()
            async with stack:
                tools = await connect_and_discover(stack, config)

        assert len(tools) == 1
        assert tools[0].name == "test-fs::test_tool"
        mock_session.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sse_connect_success(self) -> None:
        """验证 SSE 连接流程。"""
        mock_tool = MagicMock()
        mock_tool.name = "query"
        mock_tool.description = "Run query"
        mock_tool.inputSchema = {"type": "object", "properties": {"sql": {"type": "string"}}}

        mock_response = MagicMock()
        mock_response.tools = [mock_tool]

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_transport = (MagicMock(), MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("mcp.client.sse.sse_client", return_value=mock_ctx),
            patch("mcp.ClientSession", return_value=mock_session),
        ):
            config = MCPServerConfig(name="remote-db", transport="sse", url="http://db.local/sse")
            stack = AsyncExitStack()
            async with stack:
                tools = await connect_and_discover(stack, config)

        assert len(tools) == 1
        assert tools[0].name == "remote-db::query"

    @pytest.mark.asyncio
    async def test_http_connect_success(self) -> None:
        """验证 HTTP 连接流程。"""
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search docs"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        mock_response = MagicMock()
        mock_response.tools = [mock_tool]

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # streamable_http_client 返回 3 个元素 (read, write, session_id)
        mock_transport = (MagicMock(), MagicMock(), MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("mcp.client.streamable_http.streamable_http_client", return_value=mock_ctx),
            patch("mcp.ClientSession", return_value=mock_session),
        ):
            config = MCPServerConfig(name="http-search", transport="http", url="http://search.local/mcp")
            stack = AsyncExitStack()
            async with stack:
                tools = await connect_and_discover(stack, config)

        assert len(tools) == 1
        assert tools[0].name == "http-search::search"

    @pytest.mark.asyncio
    async def test_connect_failure_returns_empty(self) -> None:
        """连接异常返回空列表而非抛出。"""
        with patch(
            "mcp.client.stdio.stdio_client",
            side_effect=ConnectionError("refused"),
        ):
            config = MCPServerConfig(name="fail", transport="stdio", command="bad-cmd")
            stack = AsyncExitStack()
            async with stack:
                tools = await connect_and_discover(stack, config)

        assert tools == []

    @pytest.mark.asyncio
    async def test_multiple_tools_discovered(self) -> None:
        """验证同一 Server 可发现多个工具。"""
        mock_tools = []
        for i in range(5):
            t = MagicMock()
            t.name = f"tool_{i}"
            t.description = f"Tool {i}"
            t.inputSchema = {"type": "object", "properties": {}}
            mock_tools.append(t)

        mock_response = MagicMock()
        mock_response.tools = mock_tools

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_response)
        mock_ctx, mock_session = _make_mock_stdio_context(mock_session)

        with (
            patch("mcp.client.stdio.stdio_client", return_value=mock_ctx),
            patch("mcp.ClientSession", return_value=mock_session),
        ):
            config = MCPServerConfig(name="multi", transport="stdio", command="multi-server")
            stack = AsyncExitStack()
            async with stack:
                tools = await connect_and_discover(stack, config)

        assert len(tools) == 5
        assert all(t.name.startswith("multi::") for t in tools)


# ---------------------------------------------------------------------------
# FunctionTool **kwargs 修复验证
# ---------------------------------------------------------------------------


class TestFunctionToolKwargsPassthrough:
    """验证 FunctionTool.execute 正确传递参数到 **kwargs 函数。"""

    @pytest.mark.asyncio
    async def test_kwargs_function_receives_all_arguments(self) -> None:
        captured: dict[str, object] = {}

        async def my_fn(**kwargs: object) -> str:
            captured.update(kwargs)
            return "ok"

        tool = FunctionTool(
            name="test",
            description="test",
            fn=my_fn,
            parameters_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        )

        result = await tool.execute({"x": 42, "y": "hello"})

        assert result == "ok"
        assert captured["x"] == 42
        assert captured["y"] == "hello"
