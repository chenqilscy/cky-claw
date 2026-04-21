"""ToolSearchTool — 延迟加载元工具。

当 Agent 注册的工具数 > threshold（默认 20）时，自动替换为 search_tools 元工具，
减少 Prompt Token 消耗。LLM 通过调用 search_tools(query) 按名称/描述搜索匹配的工具，
再在后续轮次中调用实际工具。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kasaya.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

# 默认阈值：工具总数超过此值时启用 ToolSearchTool
DEFAULT_TOOL_SEARCH_THRESHOLD = 20


@dataclass
class ToolSearchTool:
    """Tool Search 元工具 — 将大量工具的 schema 替换为单一搜索入口。

    Attributes:
        tools: 被管理的所有工具列表
        threshold: 启用搜索的工具数阈值
        max_results: 搜索返回的最大工具数
    """

    tools: list[FunctionTool] = field(default_factory=list)
    threshold: int = DEFAULT_TOOL_SEARCH_THRESHOLD
    max_results: int = 5

    def should_activate(self) -> bool:
        """判断是否应启用工具搜索模式。"""
        return len(self.tools) > self.threshold

    def build_search_tool(self) -> FunctionTool:
        """构建 search_tools FunctionTool。"""
        tool_index = self._build_index()

        async def search_tools(query: str) -> str:
            """搜索可用工具。根据关键词匹配工具名称和描述，返回匹配的工具列表。

            Args:
                query: 搜索关键词

            Returns:
                匹配的工具列表（JSON 格式）
            """
            query_lower = query.lower()
            scored: list[tuple[float, dict[str, str]]] = []

            for tool_info in tool_index:
                name = tool_info["name"].lower()
                desc = tool_info["description"].lower()

                score = 0.0
                # 名称精确匹配
                if query_lower == name:
                    score = 10.0
                # 名称包含
                elif query_lower in name:
                    score = 5.0
                # 描述包含
                if query_lower in desc:
                    score += 3.0
                # 各关键词单独匹配
                for word in query_lower.split():
                    if word in name:
                        score += 2.0
                    if word in desc:
                        score += 1.0

                if score > 0:
                    scored.append((score, tool_info))

            # 按分数降序
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [item for _, item in scored[:self.max_results]]

            if not results:
                return f"No tools found matching '{query}'. Available tool count: {len(tool_index)}"

            lines = [f"Found {len(results)} tool(s) matching '{query}':\n"]
            for r in results:
                lines.append(f"- **{r['name']}**: {r['description']}")
                if r.get("parameters"):
                    lines.append(f"  Parameters: {r['parameters']}")
            return "\n".join(lines)

        return FunctionTool(
            name="search_tools",
            description=(
                f"Search through {len(self.tools)} available tools by keyword. "
                "Use this to find the right tool before calling it."
            ),
            fn=search_tools,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword to match tool names and descriptions",
                    },
                },
                "required": ["query"],
            },
        )

    def get_active_tools(self) -> list[FunctionTool]:
        """如果工具数超过阈值，返回 [search_tools]；否则原样返回。"""
        if not self.should_activate():
            return self.tools
        return [self.build_search_tool()]

    def get_full_tools(self) -> list[FunctionTool]:
        """返回所有原始工具（用于实际执行时查找）。"""
        return self.tools

    def _build_index(self) -> list[dict[str, str]]:
        """构建工具索引。"""
        index: list[dict[str, str]] = []
        for tool in self.tools:
            props = tool.parameters_schema.get("properties", {})
            param_str = ", ".join(f"{k}: {v.get('type', '?')}" for k, v in props.items()) if props else ""
            index.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": param_str,
            })
        return index
