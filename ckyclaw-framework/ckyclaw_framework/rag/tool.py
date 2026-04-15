"""RAG Tool — 将知识库检索包装为 Agent 可调用工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ckyclaw_framework.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from ckyclaw_framework.rag.pipeline import RAGPipeline


def create_knowledge_base_tool(
    pipeline: RAGPipeline,
    *,
    name: str = "knowledge_base_search",
    description: str = "搜索知识库中的相关文档片段。当需要查询文档、手册、FAQ 等知识库内容时使用此工具。",
    top_k: int = 5,
    min_score: float = 0.0,
    filter_metadata: dict[str, Any] | None = None,
) -> FunctionTool:
    """创建知识库检索工具，供 Agent 在对话中调用。

    Args:
        pipeline: RAG 管线实例。
        name: 工具名称。
        description: 工具描述（LLM 用来判断何时调用）。
        top_k: 每次检索返回的最大结果数。
        min_score: 最低相似度阈值。
        filter_metadata: 可选的元数据过滤条件。

    Returns:
        FunctionTool 实例。

    用法::

        tool = create_knowledge_base_tool(pipeline, top_k=3)
        agent = Agent(
            name="FAQ Bot",
            tools=[tool],
        )
    """

    async def _search(query: str) -> str:
        """搜索知识库中的相关文档片段。

        Args:
            query: 检索查询文本。

        Returns:
            检索到的文档片段汇总。
        """
        result = await pipeline.retrieve(
            query,
            top_k=top_k,
            min_score=min_score,
            filter_metadata=filter_metadata,
        )
        if not result.results:
            return "未在知识库中找到相关内容。"

        parts: list[str] = []
        for i, r in enumerate(result.results, 1):
            source = r.metadata.get("source", "")
            source_info = f" (来源: {source})" if source else ""
            parts.append(f"[{i}]{source_info} {r.content}")
        return "\n\n".join(parts)

    return FunctionTool(
        name=name,
        description=description,
        fn=_search,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询文本",
                },
            },
            "required": ["query"],
        },
    )
