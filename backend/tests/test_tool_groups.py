"""Tool Group 后端集成测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------


class TestToolGroupSchemas:
    def test_create_schema(self) -> None:
        from app.schemas.tool_group import ToolGroupCreate

        data = ToolGroupCreate(
            name="web-search",
            description="Web search tools",
            tools=[
                {"name": "search", "description": "Search web", "parameters_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
            ],
        )
        assert data.name == "web-search"
        assert len(data.tools) == 1

    def test_create_schema_name_validation(self) -> None:
        from app.schemas.tool_group import ToolGroupCreate

        with pytest.raises(Exception):
            ToolGroupCreate(name="AB")  # 太短且大写

    def test_update_schema_optional(self) -> None:
        from app.schemas.tool_group import ToolGroupUpdate

        data = ToolGroupUpdate(description="Updated")
        assert data.description == "Updated"
        assert data.tools is None

    def test_response_schema(self) -> None:
        from datetime import datetime, timezone
        from app.schemas.tool_group import ToolGroupResponse

        data = ToolGroupResponse(
            id="00000000-0000-0000-0000-000000000001",
            name="web-search",
            description="Search",
            tools=[{"name": "s", "description": "d", "parameters_schema": {}}],
            source="custom",
            is_enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert data.name == "web-search"


# ---------------------------------------------------------------------------
# Service 测试
# ---------------------------------------------------------------------------


class TestToolGroupService:
    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        from app.services.tool_group import list_tool_groups

        db = AsyncMock()
        # count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        # data query
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        groups, total = await list_tool_groups(db)
        assert total == 0
        assert groups == []

    @pytest.mark.asyncio
    async def test_get_not_found(self) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.tool_group import get_tool_group_by_name

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await get_tool_group_by_name(db, "nonexistent")


# ---------------------------------------------------------------------------
# _resolve_tool_groups 测试
# ---------------------------------------------------------------------------


class TestResolveToolGroups:
    @pytest.mark.asyncio
    async def test_no_tool_groups(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.tool_groups = []
        db = AsyncMock()

        result = await _resolve_tool_groups(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_resolve_single_group(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["web-search"]

        tg = MagicMock()
        tg.name = "web-search"
        tg.tools = [
            {"name": "search", "description": "Search web", "parameters_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
            {"name": "fetch", "description": "Fetch page", "parameters_schema": {"type": "object", "properties": {}}},
        ]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tg]
        db.execute = AsyncMock(return_value=mock_result)

        tools = await _resolve_tool_groups(db, config)
        assert len(tools) == 2
        assert all(isinstance(t, FunctionTool) for t in tools)
        assert tools[0].name == "search"
        assert tools[0].group == "web-search"
        assert tools[1].name == "fetch"

    @pytest.mark.asyncio
    async def test_missing_group_skipped(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["nonexistent"]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        tools = await _resolve_tool_groups(db, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_multiple_groups_combined(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["search", "file-ops"]

        tg1 = MagicMock()
        tg1.name = "search"
        tg1.tools = [{"name": "web_search", "description": "Search", "parameters_schema": {}}]

        tg2 = MagicMock()
        tg2.name = "file-ops"
        tg2.tools = [{"name": "read_file", "description": "Read", "parameters_schema": {}}]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tg1, tg2]
        db.execute = AsyncMock(return_value=mock_result)

        tools = await _resolve_tool_groups(db, config)
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"web_search", "read_file"}

    @pytest.mark.asyncio
    async def test_empty_tools_in_group(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["empty-group"]

        tg = MagicMock()
        tg.name = "empty-group"
        tg.tools = []

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tg]
        db.execute = AsyncMock(return_value=mock_result)

        tools = await _resolve_tool_groups(db, config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_invalid_tool_definition_skipped(self) -> None:
        """工具定义缺少 name 时被安全跳过。"""
        from app.services.session import _resolve_tool_groups

        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["bad-group"]

        tg = MagicMock()
        tg.name = "bad-group"
        tg.tools = [
            {"description": "No name field"},  # 缺少 name
            {"name": "valid", "description": "OK", "parameters_schema": {}},
        ]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tg]
        db.execute = AsyncMock(return_value=mock_result)

        tools = await _resolve_tool_groups(db, config)
        assert len(tools) == 1
        assert tools[0].name == "valid"
