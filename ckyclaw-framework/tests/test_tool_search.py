"""ToolSearchTool 单元测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tools.tool_search import DEFAULT_TOOL_SEARCH_THRESHOLD, ToolSearchTool


def _make_tool(name: str, desc: str = "", params: dict | None = None) -> FunctionTool:
    """辅助：创建一个简单的 FunctionTool。"""

    async def _noop() -> str:
        return "ok"

    return FunctionTool(
        name=name,
        description=desc or f"Description for {name}",
        fn=_noop,
        parameters_schema=params or {"type": "object", "properties": {}, "required": []},
    )


class TestToolSearchToolBasic:
    """ToolSearchTool 基本功能测试。"""

    def test_should_activate_below_threshold(self) -> None:
        """工具数低于阈值时不启用搜索。"""
        tst = ToolSearchTool(tools=[_make_tool(f"t{i}") for i in range(5)])
        assert not tst.should_activate()

    def test_should_activate_at_threshold(self) -> None:
        """工具数等于阈值时不启用搜索。"""
        tst = ToolSearchTool(tools=[_make_tool(f"t{i}") for i in range(DEFAULT_TOOL_SEARCH_THRESHOLD)])
        assert not tst.should_activate()

    def test_should_activate_above_threshold(self) -> None:
        """工具数超过阈值时启用搜索。"""
        tst = ToolSearchTool(tools=[_make_tool(f"t{i}") for i in range(DEFAULT_TOOL_SEARCH_THRESHOLD + 1)])
        assert tst.should_activate()

    def test_should_activate_custom_threshold(self) -> None:
        """自定义阈值。"""
        tst = ToolSearchTool(tools=[_make_tool(f"t{i}") for i in range(4)], threshold=3)
        assert tst.should_activate()

    def test_empty_tools(self) -> None:
        """空工具列表不应启用搜索。"""
        tst = ToolSearchTool(tools=[])
        assert not tst.should_activate()


class TestGetActiveTools:
    """get_active_tools 返回值测试。"""

    def test_below_threshold_returns_original(self) -> None:
        """阈值以下返回原始工具。"""
        tools = [_make_tool(f"t{i}") for i in range(3)]
        tst = ToolSearchTool(tools=tools, threshold=5)
        result = tst.get_active_tools()
        assert result == tools

    def test_above_threshold_returns_search_tool(self) -> None:
        """阈值以上返回 search_tools 元工具。"""
        tools = [_make_tool(f"t{i}") for i in range(6)]
        tst = ToolSearchTool(tools=tools, threshold=5)
        result = tst.get_active_tools()
        assert len(result) == 1
        assert result[0].name == "search_tools"

    def test_get_full_tools_always_returns_all(self) -> None:
        """get_full_tools 始终返回完整列表。"""
        tools = [_make_tool(f"t{i}") for i in range(30)]
        tst = ToolSearchTool(tools=tools)
        assert tst.should_activate()
        assert tst.get_full_tools() == tools


class TestBuildSearchTool:
    """build_search_tool 搜索功能测试。"""

    def test_build_returns_function_tool(self) -> None:
        """构建的搜索工具是 FunctionTool。"""
        tst = ToolSearchTool(tools=[_make_tool("hello")])
        result = tst.build_search_tool()
        assert isinstance(result, FunctionTool)
        assert result.name == "search_tools"

    def test_search_tool_schema(self) -> None:
        """搜索工具具有正确的参数 schema。"""
        tst = ToolSearchTool(tools=[_make_tool("hello")])
        result = tst.build_search_tool()
        assert "query" in result.parameters_schema["properties"]
        assert "query" in result.parameters_schema["required"]

    @pytest.mark.asyncio
    async def test_search_exact_name_match(self) -> None:
        """精确名称匹配优先级最高。"""
        tools = [_make_tool("calculator", "Math operations"), _make_tool("calendar", "Date tool")]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("calculator")
        assert "calculator" in result
        assert "Math operations" in result

    @pytest.mark.asyncio
    async def test_search_partial_name_match(self) -> None:
        """名称包含匹配。"""
        tools = [_make_tool("web_search", "Search the web"), _make_tool("file_read", "Read files")]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("search")
        assert "web_search" in result
        assert "file_read" not in result

    @pytest.mark.asyncio
    async def test_search_description_match(self) -> None:
        """描述匹配。"""
        tools = [_make_tool("my_tool", "Send email notifications")]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("email")
        assert "my_tool" in result

    @pytest.mark.asyncio
    async def test_search_no_match(self) -> None:
        """无匹配返回提示。"""
        tools = [_make_tool("alpha"), _make_tool("beta")]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("zzz_nonexistent")
        assert "No tools found" in result

    @pytest.mark.asyncio
    async def test_search_max_results(self) -> None:
        """搜索结果不超过 max_results。"""
        tools = [_make_tool(f"search_{i}", "Search related") for i in range(10)]
        tst = ToolSearchTool(tools=tools, max_results=3)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("search")
        # 最多 3 项
        assert result.count("**search_") <= 3

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self) -> None:
        """搜索大小写不敏感。"""
        tools = [_make_tool("DataLoader", "Load data from CSV")]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("dataloader")
        assert "DataLoader" in result

    @pytest.mark.asyncio
    async def test_search_multi_word_query(self) -> None:
        """多关键词搜索。"""
        tools = [
            _make_tool("send_email", "Send email to recipients"),
            _make_tool("read_file", "Read a file from disk"),
        ]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("send email")
        assert "send_email" in result

    @pytest.mark.asyncio
    async def test_search_shows_parameters(self) -> None:
        """搜索结果包含参数信息。"""
        tools = [_make_tool("calc", "Do math", {
            "type": "object",
            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
            "required": ["x", "y"],
        })]
        tst = ToolSearchTool(tools=tools)
        search_fn = tst.build_search_tool().fn
        assert search_fn is not None
        result = await search_fn("calc")
        assert "Parameters:" in result
        assert "x: number" in result


class TestBuildIndex:
    """_build_index 测试。"""

    def test_index_contains_all_tools(self) -> None:
        """索引包含所有工具。"""
        tools = [_make_tool(f"t{i}") for i in range(5)]
        tst = ToolSearchTool(tools=tools)
        index = tst._build_index()
        assert len(index) == 5
        assert {item["name"] for item in index} == {f"t{i}" for i in range(5)}

    def test_index_empty_tools(self) -> None:
        """空工具列表的索引也为空。"""
        tst = ToolSearchTool(tools=[])
        assert tst._build_index() == []

    def test_index_includes_parameters(self) -> None:
        """索引包含参数信息。"""
        tools = [_make_tool("t", "desc", {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        })]
        tst = ToolSearchTool(tools=tools)
        index = tst._build_index()
        assert "a: string" in index[0]["parameters"]
