"""GraphRetriever — 多路融合图谱检索。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kasaya.rag.graph.entity import Community, Entity, Relation
from kasaya.rag.graph.store import GraphStore

if TYPE_CHECKING:
    from kasaya.model.provider import ModelProvider
    from kasaya.model.settings import ModelSettings

logger = logging.getLogger(__name__)

_ENTITY_EXTRACT_PROMPT = """\
从以下查询中提取关键实体/概念名称，返回 JSON 数组。
只返回名称列表，不要解释。

查询：{query}

JSON 格式：["实体1", "实体2", ...]
"""


@dataclass
class RetrievalResult:
    """单条检索结果。"""

    entity: Entity | None = None
    relation: Relation | None = None
    community: Community | None = None
    score: float = 0.0
    source: str = ""  # entity_match / relation_traverse / community_summary

    @property
    def text_content(self) -> str:
        """获取文本内容（用于注入 Agent context）。"""
        parts: list[str] = []
        if self.entity:
            parts.append(f"[实体] {self.entity.name} ({self.entity.entity_type}): {self.entity.description}")
        if self.relation:
            parts.append(
                f"[关系] {self.relation.source_name} --[{self.relation.relation_type}]--> "
                f"{self.relation.target_name}: {self.relation.description}"
            )
        if self.community:
            parts.append(f"[社区] {self.community.name}: {self.community.summary}")
        return "\n".join(parts)


class GraphRetriever:
    """多路融合图谱检索器。

    三路检索融合：
    1. 实体匹配：LLM 从查询中提取关键概念 → 模糊匹配实体
    2. 关系遍历：从匹配实体出发 N 跳邻居
    3. 社区摘要：查找匹配实体所属社区的 Wiki 摘要
    """

    async def retrieve(
        self,
        query: str,
        store: GraphStore,
        kb_id: str,
        *,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
        top_k: int = 10,
        max_depth: int = 2,
        search_mode: str = "hybrid",
    ) -> list[RetrievalResult]:
        """执行多路融合检索。

        Args:
            query: 用户查询文本。
            store: 图存储实例。
            kb_id: 知识库 ID。
            model_provider: LLM 提供商。
            model: 模型名称。
            settings: 可选的模型设置。
            top_k: 返回结果数量上限。
            max_depth: 关系遍历深度。
            search_mode: 检索模式 (entity/traverse/community/hybrid)。
        """
        results: list[RetrievalResult] = []

        # 路径 1: 实体匹配
        seed_entity_ids: list[str] = []
        if search_mode in ("entity", "hybrid"):
            entity_results, seed_entity_ids = await self._entity_match(
                query, store, kb_id,
                model_provider=model_provider, model=model, settings=settings,
            )
            results.extend(entity_results)

        # 路径 2: 关系遍历
        if search_mode in ("traverse", "hybrid") and seed_entity_ids:
            traverse_results = await self._relation_traverse(
                seed_entity_ids, store, max_depth=max_depth,
            )
            results.extend(traverse_results)

        # 路径 3: 社区摘要
        if search_mode in ("community", "hybrid") and seed_entity_ids:
            community_results = await self._community_search(
                seed_entity_ids, store, kb_id,
            )
            results.extend(community_results)

        # 去重 + 排序
        return self._deduplicate_and_rank(results, top_k)

    async def _entity_match(
        self,
        query: str,
        store: GraphStore,
        kb_id: str,
        *,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> tuple[list[RetrievalResult], list[str]]:
        """路径 1: 从查询中提取关键概念，匹配实体。"""
        from kasaya.model.message import Message, MessageRole

        # 用 LLM 从查询中提取关键实体名
        key_names: list[str] = []
        try:
            prompt = _ENTITY_EXTRACT_PROMPT.format(query=query)
            response = await model_provider.chat(
                model=model,
                messages=[
                    Message(role=MessageRole.SYSTEM, content="你是一个实体提取专家，返回 JSON 数组。"),
                    Message(role=MessageRole.USER, content=prompt),
                ],
                settings=settings,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.content or "[]")
            if isinstance(data, list):
                key_names = [str(n).strip() for n in data if str(n).strip()]
            elif isinstance(data, dict):
                # 有些模型会返回 {"entities": [...]} 格式
                extracted = data.get("entities", data.get("names", []))
                if isinstance(extracted, list):
                    key_names = [str(n).strip() for n in extracted if str(n).strip()]
        except Exception as e:
            logger.debug("实体提取 LLM 调用失败: %s，退化为关键词匹配", e)
            # Fallback: 简单分词作为关键词
            key_names = [w for w in query.split() if len(w) > 1][:5]

        if not key_names:
            return [], []

        # 在 store 中模糊匹配
        results: list[RetrievalResult] = []
        matched_ids: list[str] = []

        for name in key_names:
            entities, _ = await store.query_entities(kb_id, name_contains=name, limit=5)
            for entity in entities:
                score = 0.9 if entity.name.lower() == name.lower() else 0.7
                results.append(RetrievalResult(
                    entity=entity, score=score, source="entity_match",
                ))
                # 通过 store 获取 entity id（此处用 name 模拟）
                matched_ids.append(name)

        return results, matched_ids

    async def _relation_traverse(
        self,
        seed_entity_ids: list[str],
        store: GraphStore,
        *,
        max_depth: int = 2,
    ) -> list[RetrievalResult]:
        """路径 2: 从种子实体出发 N 跳遍历。"""
        results: list[RetrievalResult] = []

        for entity_id in seed_entity_ids[:3]:  # 限制种子数量
            try:
                neighbor_result = await store.get_neighbors(
                    entity_id, max_depth=max_depth, max_nodes=20,
                )
                for entity in neighbor_result.entities:
                    # 跳过种子实体自身（已在 entity_match 中）
                    if entity.name in seed_entity_ids:
                        continue
                    results.append(RetrievalResult(
                        entity=entity,
                        score=max(0.5, 0.8 - neighbor_result.depths.get(entity_id, 1) * 0.1),
                        source="relation_traverse",
                    ))
                for relation in neighbor_result.relations:
                    results.append(RetrievalResult(
                        relation=relation,
                        score=0.6,
                        source="relation_traverse",
                    ))
            except Exception as e:
                logger.debug("邻居遍历失败 for %s: %s", entity_id, e)

        return results

    async def _community_search(
        self,
        seed_entity_ids: list[str],
        store: GraphStore,
        kb_id: str,
    ) -> list[RetrievalResult]:
        """路径 3: 查找种子实体所属社区的 Wiki 摘要。"""
        results: list[RetrievalResult] = []

        try:
            communities, _ = await store.query_communities(kb_id, limit=50)
        except Exception:
            return results

        seen_community_ids: set[str] = set()
        for community in communities:
            # 检查是否有种子实体在社区中
            for seed_id in seed_entity_ids:
                if seed_id in community.entity_names:
                    community_key = community.name + str(community.level)
                    if community_key not in seen_community_ids:
                        seen_community_ids.add(community_key)
                        results.append(RetrievalResult(
                            community=community,
                            score=0.75,
                            source="community_summary",
                        ))
                    break

        return results

    @staticmethod
    def _deduplicate_and_rank(
        results: list[RetrievalResult], top_k: int,
    ) -> list[RetrievalResult]:
        """去重 + 按分数排序 + 截断。"""
        seen: set[str] = set()
        unique: list[RetrievalResult] = []

        for r in results:
            # 构建唯一标识
            key_parts: list[str] = [r.source]
            if r.entity:
                key_parts.append(f"e:{r.entity.name}")
            elif r.relation:
                key_parts.append(f"r:{r.relation.source_name}->{r.relation.target_name}")
            elif r.community:
                key_parts.append(f"c:{r.community.name}")
            key = "|".join(key_parts)

            if key not in seen:
                seen.add(key)
                unique.append(r)

        unique.sort(key=lambda x: x.score, reverse=True)
        return unique[:top_k]
