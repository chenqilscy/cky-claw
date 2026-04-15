"""Backend MCP 集成测试 — _resolve_mcp_tools / _build_agent_from_config / execute_run。"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool

# ---------------------------------------------------------------------------
# _resolve_mcp_tools 测试
# ---------------------------------------------------------------------------


class TestResolveMCPTools:
    @pytest.mark.asyncio
    async def test_no_mcp_servers(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.mcp_servers = []
        db = AsyncMock()

        result = await _resolve_mcp_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_none_mcp_servers(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.mcp_servers = None
        db = AsyncMock()

        result = await _resolve_mcp_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_without_stack_returns_empty(self) -> None:
        """未提供 AsyncExitStack 时仅日志、不连接。"""
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "agent-1"
        config.mcp_servers = ["mcp-srv"]

        db_mcp_config = MagicMock()
        db_mcp_config.name = "mcp-srv"

        db = AsyncMock()

        with patch(
            "app.services.mcp_server.get_mcp_servers_by_names",
            new_callable=AsyncMock,
            return_value=[db_mcp_config],
        ):
            result = await _resolve_mcp_tools(db, config)

        assert result == []

    @pytest.mark.asyncio
    async def test_with_stack_calls_connect_and_discover(self) -> None:
        """提供 stack 时，逐个连接 MCP Server 并收集工具。"""
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "agent-1"
        config.mcp_servers = ["srv-a", "srv-b"]

        srv_a = MagicMock()
        srv_a.name = "srv-a"
        srv_a.transport_type = "stdio"
        srv_a.command = "npx server-a"
        srv_a.url = None
        srv_a.env = {}
        srv_a.auth_config = None

        srv_b = MagicMock()
        srv_b.name = "srv-b"
        srv_b.transport_type = "sse"
        srv_b.command = None
        srv_b.url = "http://b.local/sse"
        srv_b.env = {}
        srv_b.auth_config = None

        tool_a = FunctionTool(name="srv-a::tool1", description="T1")
        tool_b1 = FunctionTool(name="srv-b::tool2", description="T2")
        tool_b2 = FunctionTool(name="srv-b::tool3", description="T3")

        call_count = 0

        async def mock_connect(stack_arg, fw_config):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if fw_config.name == "srv-a":
                return [tool_a]
            return [tool_b1, tool_b2]

        db = AsyncMock()
        stack = AsyncExitStack()

        with (
            patch(
                "app.services.mcp_server.get_mcp_servers_by_names",
                new_callable=AsyncMock,
                return_value=[srv_a, srv_b],
            ),
            patch(
                "ckyclaw_framework.mcp.connection.connect_and_discover",
                side_effect=mock_connect,
            ),
        ):
            async with stack:
                result = await _resolve_mcp_tools(db, config, stack=stack)

        assert len(result) == 3
        assert call_count == 2
        names = {t.name for t in result}
        assert names == {"srv-a::tool1", "srv-b::tool2", "srv-b::tool3"}

    @pytest.mark.asyncio
    async def test_missing_server_warns_but_continues(self) -> None:
        """请求的 MCP Server 不在 DB 中时，跳过缺失的、处理存在的。"""
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "agent-1"
        config.mcp_servers = ["exists", "missing"]

        db_cfg = MagicMock()
        db_cfg.name = "exists"
        db_cfg.transport_type = "stdio"
        db_cfg.command = "npx server"
        db_cfg.url = None
        db_cfg.env = {}
        db_cfg.auth_config = None

        tool = FunctionTool(name="exists::t1", description="T1")

        db = AsyncMock()
        stack = AsyncExitStack()

        with (
            patch(
                "app.services.mcp_server.get_mcp_servers_by_names",
                new_callable=AsyncMock,
                return_value=[db_cfg],
            ),
            patch(
                "ckyclaw_framework.mcp.connection.connect_and_discover",
                new_callable=AsyncMock,
                return_value=[tool],
            ),
        ):
            async with stack:
                result = await _resolve_mcp_tools(db, config, stack=stack)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_auth_config_decrypted_to_headers(self) -> None:
        """auth_config 中的加密值应解密后作为 headers 传递到 FrameworkMCPConfig。"""
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "agent-1"
        config.mcp_servers = ["secured"]

        db_cfg = MagicMock()
        db_cfg.name = "secured"
        db_cfg.transport_type = "sse"
        db_cfg.command = None
        db_cfg.url = "http://secure.local/sse"
        db_cfg.env = {}
        db_cfg.auth_config = {"Authorization": "enc_xxx"}

        captured_fw_config = None

        async def capture_connect(stack_arg, fw_config):  # type: ignore[no-untyped-def]
            nonlocal captured_fw_config
            captured_fw_config = fw_config
            return []

        db = AsyncMock()
        stack = AsyncExitStack()

        with (
            patch(
                "app.services.mcp_server.get_mcp_servers_by_names",
                new_callable=AsyncMock,
                return_value=[db_cfg],
            ),
            patch(
                "ckyclaw_framework.mcp.connection.connect_and_discover",
                side_effect=capture_connect,
            ),
            patch("app.core.crypto.decrypt_api_key", return_value="Bearer real_token"),
        ):
            async with stack:
                await _resolve_mcp_tools(db, config, stack=stack)

        assert captured_fw_config is not None
        assert captured_fw_config.name == "secured"
        assert captured_fw_config.transport == "sse"
        assert captured_fw_config.headers["Authorization"] == "Bearer real_token"

    @pytest.mark.asyncio
    async def test_env_passed_through(self) -> None:
        """DB 中 MCP Server 的 env 应传递到 FrameworkMCPConfig。"""
        from app.services.session import _resolve_mcp_tools

        config = MagicMock()
        config.name = "agent-1"
        config.mcp_servers = ["env-srv"]

        db_cfg = MagicMock()
        db_cfg.name = "env-srv"
        db_cfg.transport_type = "stdio"
        db_cfg.command = "cmd"
        db_cfg.url = None
        db_cfg.env = {"API_KEY": "12345", "DEBUG": "true"}
        db_cfg.auth_config = None

        captured_fw_config = None

        async def capture_connect(stack_arg, fw_config):  # type: ignore[no-untyped-def]
            nonlocal captured_fw_config
            captured_fw_config = fw_config
            return []

        db = AsyncMock()
        stack = AsyncExitStack()

        with (
            patch(
                "app.services.mcp_server.get_mcp_servers_by_names",
                new_callable=AsyncMock,
                return_value=[db_cfg],
            ),
            patch(
                "ckyclaw_framework.mcp.connection.connect_and_discover",
                side_effect=capture_connect,
            ),
        ):
            async with stack:
                await _resolve_mcp_tools(db, config, stack=stack)

        assert captured_fw_config is not None
        assert captured_fw_config.env == {"API_KEY": "12345", "DEBUG": "true"}


# ---------------------------------------------------------------------------
# _build_agent_from_config with mcp_tools 测试
# ---------------------------------------------------------------------------


class TestBuildAgentWithMCPTools:
    def test_agent_includes_mcp_tools(self) -> None:
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "Test"
        config.instructions = "Instructions"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        mcp_tool = FunctionTool(name="srv::read_file", description="Read a file")
        agent = _build_agent_from_config(config, mcp_tools=[mcp_tool])

        assert len(agent.tools) == 1
        assert agent.tools[0].name == "srv::read_file"

    def test_agent_no_mcp_tools(self) -> None:
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "Test"
        config.instructions = "Instructions"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        agent = _build_agent_from_config(config)
        assert agent.tools == []

    def test_agent_mcp_tools_none(self) -> None:
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "Test"
        config.instructions = "Instructions"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        agent = _build_agent_from_config(config, mcp_tools=None)
        assert agent.tools == []

    def test_agent_multiple_mcp_tools(self) -> None:
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "Test"
        config.instructions = "Instructions"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        tools = [
            FunctionTool(name="srv-a::t1", description="T1"),
            FunctionTool(name="srv-b::t2", description="T2"),
        ]
        agent = _build_agent_from_config(config, mcp_tools=tools)

        assert len(agent.tools) == 2
