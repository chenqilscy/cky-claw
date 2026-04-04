"""Hosted Tool Groups seed 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tool_group import (
    _HOSTED_TOOL_GROUPS,
    seed_hosted_tool_groups,
)


class TestHostedToolGroupsSeed:
    """测试内置工具组 seed 函数。"""

    def test_hosted_groups_definition(self) -> None:
        """定义包含 5 个工具组。"""
        assert len(_HOSTED_TOOL_GROUPS) == 5
        names = {str(g["name"]) for g in _HOSTED_TOOL_GROUPS}
        assert names == {"web-search", "code-executor", "file-ops", "http", "database"}

    def test_hosted_groups_each_has_tools(self) -> None:
        """每个工具组至少有 1 个工具定义。"""
        for group in _HOSTED_TOOL_GROUPS:
            tools = group["tools"]
            assert isinstance(tools, list)
            assert len(tools) >= 1, f"工具组 {group['name']} 没有工具"

    @pytest.mark.asyncio
    async def test_seed_creates_new_groups(self) -> None:
        """首次 seed 创建所有工具组。"""
        db = AsyncMock()
        # 模拟数据库查询：所有组都不存在
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        count = await seed_hosted_tool_groups(db)
        assert count == 5
        assert db.add.call_count == 5
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_skips_existing(self) -> None:
        """已存在的工具组不重复创建。"""
        db = AsyncMock()
        # 模拟：所有组已存在
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = uuid.uuid4()
        db.execute.return_value = mock_result

        count = await seed_hosted_tool_groups(db)
        assert count == 0
        db.add.assert_not_called()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_partial_existing(self) -> None:
        """部分已存在时只创建缺少的。"""
        db = AsyncMock()
        call_count = 0

        async def mock_execute(stmt: object) -> MagicMock:
            nonlocal call_count
            result = MagicMock()
            # 前 3 个已存在，后 2 个不存在
            result.scalar_one_or_none.return_value = uuid.uuid4() if call_count < 3 else None
            call_count += 1
            return result

        db.execute = mock_execute

        count = await seed_hosted_tool_groups(db)
        assert count == 2
        assert db.add.call_count == 2

    def test_hosted_groups_have_source_hosted(self) -> None:
        """确认 seed 创建的记录 source='hosted'。"""
        # 验证 seed 函数内部使用 source="hosted"
        import inspect
        source_code = inspect.getsource(seed_hosted_tool_groups)
        assert 'source="hosted"' in source_code

    def test_all_tool_names_match_framework(self) -> None:
        """后端 seed 工具名称与 Framework 定义一致。"""
        from ckyclaw_framework.tools.hosted_tools import _build_hosted_groups

        framework_names: set[str] = set()
        for group in _build_hosted_groups():
            for tool in group.tools:
                framework_names.add(tool.name)

        backend_names: set[str] = set()
        for group in _HOSTED_TOOL_GROUPS:
            for tool in group["tools"]:  # type: ignore[union-attr]
                assert isinstance(tool, dict)
                backend_names.add(tool["name"])

        assert framework_names == backend_names, (
            f"Framework 与 Backend 工具名称不一致: "
            f"仅 Framework: {framework_names - backend_names}, "
            f"仅 Backend: {backend_names - framework_names}"
        )
