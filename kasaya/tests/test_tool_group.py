"""Tool Group 框架层测试。"""

from __future__ import annotations

from kasaya.tools.function_tool import FunctionTool
from kasaya.tools.tool_group import ToolGroup
from kasaya.tools.tool_registry import ToolRegistry, get_default_registry

# ---------------------------------------------------------------------------
# ToolGroup 测试
# ---------------------------------------------------------------------------


class TestToolGroup:
    def test_create_empty_group(self) -> None:
        group = ToolGroup(name="test-group")
        assert group.name == "test-group"
        assert group.tools == []
        assert group.description == ""

    def test_register_tool(self) -> None:
        group = ToolGroup(name="search")
        tool = FunctionTool(name="web_search", description="Web search")
        group.register(tool)
        assert len(group.tools) == 1
        assert group.tools[0].name == "web_search"

    def test_register_duplicate_overwrites(self) -> None:
        group = ToolGroup(name="search")
        tool1 = FunctionTool(name="web_search", description="v1")
        tool2 = FunctionTool(name="web_search", description="v2")
        group.register(tool1)
        group.register(tool2)
        assert len(group.tools) == 1
        assert group.tools[0].description == "v2"

    def test_get_tool(self) -> None:
        group = ToolGroup(name="search")
        group.register(FunctionTool(name="web_search", description="Search"))
        assert group.get_tool("web_search") is not None
        assert group.get_tool("nonexistent") is None

    def test_tool_names(self) -> None:
        group = ToolGroup(name="ops")
        group.register(FunctionTool(name="read_file", description="Read"))
        group.register(FunctionTool(name="write_file", description="Write"))
        assert group.tool_names() == ["read_file", "write_file"]

    def test_description(self) -> None:
        group = ToolGroup(name="web", description="Web tools")
        assert group.description == "Web tools"


# ---------------------------------------------------------------------------
# ToolRegistry 测试
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get_group(self) -> None:
        registry = ToolRegistry()
        group = ToolGroup(name="search", description="Search tools")
        registry.register_group(group)
        assert registry.get_group("search") is group

    def test_get_nonexistent_group(self) -> None:
        registry = ToolRegistry()
        assert registry.get_group("unknown") is None

    def test_list_groups(self) -> None:
        registry = ToolRegistry()
        registry.register_group(ToolGroup(name="a"))
        registry.register_group(ToolGroup(name="b"))
        groups = registry.list_groups()
        names = {g.name for g in groups}
        assert names == {"a", "b"}

    def test_register_duplicate_overwrites(self) -> None:
        registry = ToolRegistry()
        g1 = ToolGroup(name="search", description="v1")
        g2 = ToolGroup(name="search", description="v2")
        registry.register_group(g1)
        registry.register_group(g2)
        assert registry.get_group("search") is g2
        assert len(registry.list_groups()) == 1

    def test_get_tool_across_groups(self) -> None:
        registry = ToolRegistry()
        g = ToolGroup(name="search")
        g.register(FunctionTool(name="web_search", description="Search"))
        registry.register_group(g)
        assert registry.get_tool("web_search") is not None
        assert registry.get_tool("nonexistent") is None

    def test_remove_group(self) -> None:
        registry = ToolRegistry()
        registry.register_group(ToolGroup(name="temp"))
        assert registry.remove_group("temp") is True
        assert registry.get_group("temp") is None
        assert registry.remove_group("temp") is False

    def test_clear(self) -> None:
        registry = ToolRegistry()
        registry.register_group(ToolGroup(name="a"))
        registry.register_group(ToolGroup(name="b"))
        registry.clear()
        assert len(registry.list_groups()) == 0

    def test_default_registry_singleton(self) -> None:
        r1 = get_default_registry()
        r2 = get_default_registry()
        assert r1 is r2
