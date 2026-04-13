"""Agent-as-Tool 后端集成测试。"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool


# ---------------------------------------------------------------------------
# _resolve_agent_tools 测试
# ---------------------------------------------------------------------------


class TestResolveAgentTools:
    @pytest.mark.asyncio
    async def test_no_agent_tools(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.agent_tools = []
        db = AsyncMock()

        result = await _resolve_agent_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_none_agent_tools(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.agent_tools = None
        db = AsyncMock()

        result = await _resolve_agent_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_resolve_single_agent_tool(self) -> None:
        """单个 Agent-as-Tool 被正确解析为 FunctionTool。"""
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.name = "manager"
        config.agent_tools = ["analyst"]

        target_config = MagicMock()
        target_config.name = "analyst"
        target_config.description = "Analyze data"
        target_config.instructions = "You analyze data."
        target_config.model = "gpt-4o"
        target_config.model_settings = None
        target_config.guardrails = None
        target_config.approval_mode = None
        target_config.handoffs = []
        target_config.agent_tools = []

        db = AsyncMock()

        # Mock DB query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [target_config]
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_agent_tools(db, config, run_config=None)

        assert len(result) == 1
        tool = result[0]
        assert isinstance(tool, FunctionTool)
        assert tool.name == "analyst"
        assert "Analyze data" in tool.description

    @pytest.mark.asyncio
    async def test_cycle_detection(self) -> None:
        """检测循环引用：A→B→A，不会无限递归。"""
        from app.services.session import _resolve_agent_tools

        config_a = MagicMock()
        config_a.name = "agent-a"
        config_a.agent_tools = ["agent-b"]

        config_b = MagicMock()
        config_b.name = "agent-b"
        config_b.description = "B"
        config_b.instructions = "B"
        config_b.model = "gpt-4o"
        config_b.model_settings = None
        config_b.guardrails = None
        config_b.approval_mode = None
        config_b.handoffs = []
        config_b.agent_tools = ["agent-a"]  # 循环引用

        db = AsyncMock()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.scalars.return_value.all.return_value = [config_b] if call_count == 1 else []
            return result

        db.execute = mock_execute

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            tools = await _resolve_agent_tools(db, config_a, run_config=None)

        # agent-b 被解析，但 agent-b 的 agent_tools (agent-a) 被循环检测跳过
        assert len(tools) == 1
        assert tools[0].name == "agent-b"

    @pytest.mark.asyncio
    async def test_depth_limit(self) -> None:
        """深度超限时截断，不会无限递归。"""
        from app.services.session import _MAX_AGENT_TOOL_DEPTH, _resolve_agent_tools

        config = MagicMock()
        config.name = "deep"
        config.agent_tools = ["sub"]

        db = AsyncMock()

        # 直接超深度调用
        tools = await _resolve_agent_tools(db, config, depth=_MAX_AGENT_TOOL_DEPTH)
        assert tools == []

    @pytest.mark.asyncio
    async def test_missing_agent_skipped(self) -> None:
        """目标 Agent 不存在时安全跳过。"""
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.name = "manager"
        config.agent_tools = ["nonexistent"]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            tools = await _resolve_agent_tools(db, config, run_config=None)

        assert tools == []

    @pytest.mark.asyncio
    async def test_multiple_agent_tools(self) -> None:
        """多个 Agent-as-Tool 全部被解析。"""
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.name = "manager"
        config.agent_tools = ["analyst", "reviewer"]

        analyst = MagicMock()
        analyst.name = "analyst"
        analyst.description = "Analyst"
        analyst.instructions = "Analyze"
        analyst.model = "gpt-4o"
        analyst.model_settings = None
        analyst.guardrails = None
        analyst.approval_mode = None
        analyst.handoffs = []
        analyst.agent_tools = []

        reviewer = MagicMock()
        reviewer.name = "reviewer"
        reviewer.description = "Reviewer"
        reviewer.instructions = "Review"
        reviewer.model = "gpt-4o"
        reviewer.model_settings = None
        reviewer.guardrails = None
        reviewer.approval_mode = None
        reviewer.handoffs = []
        reviewer.agent_tools = []

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [analyst, reviewer]
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            tools = await _resolve_agent_tools(db, config, run_config=None)

        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert tool_names == {"analyst", "reviewer"}


# ---------------------------------------------------------------------------
# _build_agent_from_config with agent_tools 测试
# ---------------------------------------------------------------------------


class TestBuildAgentWithAgentTools:
    def test_agent_tools_combined_with_mcp_tools(self) -> None:
        """agent_tools 和 mcp_tools 应合并在一起。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "manager"
        config.description = "Manager"
        config.instructions = "Manage"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        mcp_tool = FunctionTool(name="mcp::search", description="Search")
        agent_tool = FunctionTool(name="analyst", description="Analyst tool")

        agent = _build_agent_from_config(config, mcp_tools=[mcp_tool, agent_tool])
        assert len(agent.tools) == 2


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestAgentSchemaWithAgentTools:
    def test_create_schema_accepts_agent_tools(self) -> None:
        from app.schemas.agent import AgentCreate

        data = AgentCreate(name="test-manager", agent_tools=["sub-a", "sub-b"])
        assert data.agent_tools == ["sub-a", "sub-b"]

    def test_create_schema_defaults_empty(self) -> None:
        from app.schemas.agent import AgentCreate

        data = AgentCreate(name="test-agent")
        assert data.agent_tools == []

    def test_update_schema_optional(self) -> None:
        from app.schemas.agent import AgentUpdate

        data = AgentUpdate(agent_tools=["new-agent"])
        assert data.agent_tools == ["new-agent"]

    def test_response_schema_includes_agent_tools(self) -> None:
        from datetime import datetime, timezone

        from app.schemas.agent import AgentResponse

        data = AgentResponse(
            id="00000000-0000-0000-0000-000000000001",
            name="test",
            description="",
            instructions="",
            model=None,
            provider_name=None,
            model_settings=None,
            tool_groups=[],
            handoffs=[],
            guardrails={},
            approval_mode="suggest",
            mcp_servers=[],
            agent_tools=["sub-a"],
            skills=[],
            output_type=None,
            metadata_={},
            prompt_variables=[],
            response_style=None,
            org_id=None,
            is_active=True,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert data.agent_tools == ["sub-a"]
