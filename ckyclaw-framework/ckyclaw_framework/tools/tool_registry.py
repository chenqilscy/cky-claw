"""ToolRegistry — 全局工具注册表，管理所有 ToolGroup。"""

from __future__ import annotations

import logging

from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tools.tool_group import ToolGroup

logger = logging.getLogger(__name__)


class ToolRegistry:
    """全局工具注册表。管理所有 ToolGroup 和 FunctionTool。"""

    def __init__(self) -> None:
        self._groups: dict[str, ToolGroup] = {}

    def register_group(self, group: ToolGroup) -> None:
        """注册工具组。如果同名组已存在，则覆盖。"""
        if group.name in self._groups:
            logger.warning("工具组 '%s' 已存在，将覆盖", group.name)
        self._groups[group.name] = group

    def get_group(self, name: str) -> ToolGroup | None:
        """按名称获取工具组。"""
        return self._groups.get(name)

    def list_groups(self) -> list[ToolGroup]:
        """列出所有已注册工具组。"""
        return list(self._groups.values())

    def get_tool(self, name: str) -> FunctionTool | None:
        """按名称在所有组中查找工具。"""
        for group in self._groups.values():
            tool = group.get_tool(name)
            if tool is not None:
                return tool
        return None

    def remove_group(self, name: str) -> bool:
        """移除工具组。返回 True 如果存在并移除。"""
        return self._groups.pop(name, None) is not None

    def clear(self) -> None:
        """清空所有注册。"""
        self._groups.clear()


# 全局单例
_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """获取全局默认 ToolRegistry 单例。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
    return _default_registry
