"""CommunityDetector — 图社区检测 + LLM 摘要生成。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.rag.graph.entity import Community, Entity, Relation

if TYPE_CHECKING:
    from ckyclaw_framework.model.provider import ModelProvider
    from ckyclaw_framework.model.settings import ModelSettings

logger = logging.getLogger(__name__)

_COMMUNITY_SUMMARY_PROMPT = """\
你是一个知识图谱分析专家。以下是一个图社区（紧密相关的实体群组）的内容。

社区内实体：
{entities_text}

社区内关系：
{relations_text}

请生成：
1. 一个简洁的社区标题（10字以内）
2. 一段 Wiki 式摘要（100-200字，概括这个社区的核心主题和关键关系）

以 JSON 格式返回：
{{"title": "...", "summary": "..."}}
"""


class CommunityDetector:
    """图社区检测 + LLM 摘要生成。

    使用 python-igraph 的 Leiden 算法进行社区检测，
    然后通过 LLM 为每个社区生成 Wiki 式摘要。

    Args:
        resolution: Leiden 算法的分辨率参数。
            越大社区越多越小（细粒度），越小社区越少越大（粗粒度）。默认 1.0。
    """

    def __init__(self, resolution: float = 1.0) -> None:
        self._resolution = resolution

    async def detect(
        self,
        entities: list[Entity],
        relations: list[Relation],
        *,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> list[Community]:
        """检测社区并生成 Wiki 摘要。

        Args:
            entities: 全部实体列表。
            relations: 全部关系列表。
            model_provider: LLM 提供商。
            model: 模型名称。
            settings: 可选的模型设置。

        Returns:
            社区列表。
        """
        if not entities:
            return []

        try:
            return await self._detect_with_leiden(
                entities, relations,
                model_provider=model_provider, model=model, settings=settings,
            )
        except ImportError:
            logger.warning("python-igraph 未安装，退化为按实体类型分组")
            return self._fallback_by_type(entities)
        except Exception as e:
            logger.warning("Leiden 社区检测失败 (%s)，退化为连通分量", e)
            return self._fallback_connected(entities, relations)

    async def _detect_with_leiden(
        self,
        entities: list[Entity],
        relations: list[Relation],
        *,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> list[Community]:
        """使用 igraph Leiden 算法检测社区。"""
        import igraph  # type: ignore[import-untyped]

        if not relations:
            return self._fallback_by_type(entities)

        # 构建 name -> index 映射
        name_to_idx: dict[str, int] = {}
        for i, entity in enumerate(entities):
            name_to_idx[entity.name] = i

        # 构建 igraph
        g = igraph.Graph(len(entities))
        g.vs["name"] = [e.name for e in entities]
        g.vs["entity_type"] = [e.entity_type for e in entities]

        edges: list[tuple[int, int]] = []
        weights: list[float] = []
        for rel in relations:
            src = name_to_idx.get(rel.source_name)
            tgt = name_to_idx.get(rel.target_name)
            if src is not None and tgt is not None and src != tgt:
                edges.append((src, tgt))
                weights.append(rel.weight)

        g.add_edges(edges)
        if weights:
            g.es["weight"] = weights

        # Leiden 社区检测
        try:
            partition = g.community_leiden(
                resolution=self._resolution,
                weights="weight" if weights else None,
                n_iterations=10,
            )
        except Exception as e:
            logger.warning("Leiden 算法异常: %s，退化为连通分量", e)
            return self._fallback_connected(entities, relations)

        # 组装社区
        communities: list[Community] = []
        for membership in partition:
            member_entities = [entities[i] for i in membership if i < len(entities)]
            if not member_entities:
                continue

            member_names = {e.name for e in member_entities}
            member_relations = [
                r for r in relations
                if r.source_name in member_names or r.target_name in member_names
            ]

            # 生成社区摘要
            title, summary = await self._generate_summary(
                member_entities, member_relations,
                model_provider=model_provider, model=model, settings=settings,
            )

            communities.append(Community(
                name=title,
                summary=summary,
                entity_names=[e.name for e in member_entities],
                level=0,
            ))

        if not communities:
            return self._fallback_by_type(entities)

        return communities

    async def _generate_summary(
        self,
        entities: list[Entity],
        relations: list[Relation],
        *,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> tuple[str, str]:
        """用 LLM 为社区生成标题和摘要。"""
        import json

        from ckyclaw_framework.model.message import Message, MessageRole

        entities_text = "\n".join(
            f"- {e.name} ({e.entity_type}): {e.description}"
            for e in entities[:30]  # 限制数量避免 token 过多
        )
        relations_text = "\n".join(
            f"- {r.source_name} --[{r.relation_type}]--> {r.target_name}: {r.description}"
            for r in relations[:30]
        )

        prompt = _COMMUNITY_SUMMARY_PROMPT.format(
            entities_text=entities_text,
            relations_text=relations_text,
        )

        try:
            response = await model_provider.chat(
                model=model,
                messages=[
                    Message(role=MessageRole.SYSTEM, content="你是知识图谱分析专家，返回严格的 JSON。"),
                    Message(role=MessageRole.USER, content=prompt),
                ],
                settings=settings,
                response_format={"type": "json_object"},
            )

            data = json.loads(response.content or "{}")
            title = data.get("title", entities[0].entity_type if entities else "未命名社区")
            summary = data.get("summary", "、".join(e.name for e in entities[:5]))
            return str(title), str(summary)

        except Exception as e:
            logger.debug("社区摘要 LLM 调用失败: %s，使用规则生成", e)
            # Fallback: 规则生成摘要
            names = [e.name for e in entities[:5]]
            title = f"{entities[0].entity_type}社区" if entities else "未知社区"
            summary = f"包含实体：{'、'.join(names)}"
            if len(entities) > 5:
                summary += f" 等 {len(entities)} 个实体"
            return title, summary

    def _fallback_by_type(self, entities: list[Entity]) -> list[Community]:
        """Fallback: 按实体类型分组。"""
        from collections import defaultdict

        groups: dict[str, list[Entity]] = defaultdict(list)
        for entity in entities:
            groups[entity.entity_type].append(entity)

        communities: list[Community] = []
        for etype, group in groups.items():
            communities.append(Community(
                name=f"{etype}社区",
                summary=f"包含 {len(group)} 个 {etype} 类型实体：" + "、".join(e.name for e in group[:5]),
                entity_names=[e.name for e in group],
                level=0,
            ))
        return communities

    def _fallback_connected(self, entities: list[Entity], relations: list[Relation]) -> list[Community]:
        """Fallback: 简单连通分量分组。"""
        if not relations:
            return self._fallback_by_type(entities)

        # Union-Find
        parent: dict[str, str] = {e.name: e.name for e in entities}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for rel in relations:
            if rel.source_name in parent and rel.target_name in parent:
                union(rel.source_name, rel.target_name)

        from collections import defaultdict
        groups: dict[str, list[Entity]] = defaultdict(list)
        entity_map = {e.name: e for e in entities}
        for name in parent:
            root = find(name)
            if name in entity_map:
                groups[root].append(entity_map[name])

        communities: list[Community] = []
        for root, group in groups.items():
            communities.append(Community(
                name=f"社区-{root[:8]}",
                summary=f"包含 {len(group)} 个实体：" + "、".join(e.name for e in group[:5]),
                entity_names=[e.name for e in group],
                level=0,
            ))
        return communities
