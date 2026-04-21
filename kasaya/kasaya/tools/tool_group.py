"""ToolGroup — 工具组，按功能分组的工具集合。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kasaya.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)


@dataclass
class ToolGroup:
    """工具组——按功能分组的工具集合。"""

    name: str
    """组名（如 web-search、code-executor）"""

    tools: list[FunctionTool] = field(default_factory=list)
    """组内工具列表"""

    description: str = ""
    """组描述"""

    def register(self, tool: FunctionTool) -> None:
        """注册工具到此组。"""
        for existing in self.tools:
            if existing.name == tool.name:
                logger.warning("工具组 '%s' 中工具 '%s' 已存在，将覆盖", self.name, tool.name)
                self.tools.remove(existing)
                break
        self.tools.append(tool)

    def get_tool(self, name: str) -> FunctionTool | None:
        """按名称查找组内工具。"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def tool_names(self) -> list[str]:
        """返回组内所有工具名称。"""
        return [t.name for t in self.tools]
