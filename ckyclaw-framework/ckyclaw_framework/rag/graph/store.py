"""GraphStore — 图存储抽象层 + 内存实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ckyclaw_framework.rag.graph.entity import Community, Entity, Relation


@dataclass
class NeighborResult:
    """邻居查询结果。"""

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    depths: dict[str, int] = field(default_factory=dict)  # entity_id -> depth


@dataclass
class GraphData:
    """图谱可视化数据。"""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


class GraphStore(ABC):
    """图存储抽象基类。

    实现可以是内存（InMemoryGraphStore）、PostgreSQL（后端 ORM）等。
    框架层只定义 ABC，后端层提供 PG 实现。
    """

    @abstractmethod
    async def add_entities(self, kb_id: str, entities: list[Entity], document_id: str) -> list[str]:
        """添加实体，返回实体 ID 列表。"""
        ...

    @abstractmethod
    async def add_relations(
        self, kb_id: str, relations: list[Relation], name_to_id: dict[str, str]
    ) -> list[str]:
        """添加关系，返回关系 ID 列表。name_to_id 用于将实体名解析为 ID。"""
        ...

    @abstractmethod
    async def add_communities(self, kb_id: str, communities: list[Community]) -> list[str]:
        """添加社区，返回社区 ID 列表。"""
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None:
        """获取单个实体。"""
        ...

    @abstractmethod
    async def get_neighbors(
        self, entity_id: str, *, max_depth: int = 1, max_nodes: int = 50
    ) -> NeighborResult:
        """获取实体的 N 跳邻居。"""
        ...

    @abstractmethod
    async def query_entities(
        self,
        kb_id: str,
        *,
        name_contains: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Entity], int]:
        """条件查询实体，返回 (列表, 总数)。"""
        ...

    @abstractmethod
    async def query_relations(
        self,
        kb_id: str,
        *,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Relation], int]:
        """条件查询关系，返回 (列表, 总数)。"""
        ...

    @abstractmethod
    async def query_communities(
        self,
        kb_id: str,
        *,
        level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Community], int]:
        """条件查询社区，返回 (列表, 总数)。"""
        ...

    @abstractmethod
    async def get_graph_data(self, kb_id: str, *, max_nodes: int = 200) -> GraphData:
        """获取图谱可视化数据（nodes + edges）。"""
        ...

    @abstractmethod
    async def delete_by_document(self, kb_id: str, document_id: str) -> int:
        """删除指定文档的所有图谱数据，返回删除数量。"""
        ...

    @abstractmethod
    async def delete_all(self, kb_id: str) -> int:
        """清空知识库的所有图谱数据，返回删除数量。"""
        ...

    @abstractmethod
    async def merge_entities(self, kb_id: str, entities: list[Entity]) -> dict[str, str]:
        """消歧合并实体，返回 name -> id 映射。

        同名同类型的实体会被合并：
        - attributes 深度合并
        - confidence 取 max
        - description 保留更长的
        - source_chunk 合并
        """
        ...

    @abstractmethod
    async def entity_count(self, kb_id: str) -> int:
        """返回实体总数。"""
        ...

    @abstractmethod
    async def relation_count(self, kb_id: str) -> int:
        """返回关系总数。"""
        ...

    @abstractmethod
    async def community_count(self, kb_id: str) -> int:
        """返回社区总数。"""
        ...


class InMemoryGraphStore(GraphStore):
    """内存图存储，用于测试。"""

    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Entity]] = defaultdict(dict)  # kb_id -> {id: Entity}
        self._relations: dict[str, dict[str, Relation]] = defaultdict(dict)
        self._communities: dict[str, dict[str, Community]] = defaultdict(dict)
        # 复合 key (name, entity_type) -> entity_id，支持同名不同类型
        self._entity_key_to_id: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
        self._entity_by_doc: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._next_id = 0

    def _gen_id(self) -> str:
        self._next_id += 1
        return f"entity-{self._next_id}"

    def _build_name_to_id_map(self, kb_id: str) -> dict[str, str]:
        """构建 name -> id 映射（同名不同类型时取最后一个）。"""
        result: dict[str, str] = {}
        for (name, _etype), eid in self._entity_key_to_id.get(kb_id, {}).items():
            result[name] = eid
        return result

    async def add_entities(self, kb_id: str, entities: list[Entity], document_id: str) -> list[str]:
        ids: list[str] = []
        for entity in entities:
            eid = self._gen_id()
            self._entities[kb_id][eid] = entity
            self._entity_key_to_id[kb_id][(entity.name, entity.entity_type)] = eid
            self._entity_by_doc[kb_id][document_id].add(eid)
            ids.append(eid)
        return ids

    async def add_relations(
        self, kb_id: str, relations: list[Relation], name_to_id: dict[str, str]
    ) -> list[str]:
        ids: list[str] = []
        for rel in relations:
            rid = self._gen_id()
            self._relations[kb_id][rid] = rel
            ids.append(rid)
        return ids

    async def add_communities(self, kb_id: str, communities: list[Community]) -> list[str]:
        ids: list[str] = []
        for community in communities:
            cid = self._gen_id()
            self._communities[kb_id][cid] = community
            ids.append(cid)
        return ids

    async def get_entity(self, entity_id: str) -> Entity | None:
        for kb_entities in self._entities.values():
            if entity_id in kb_entities:
                return kb_entities[entity_id]
        return None

    async def get_neighbors(
        self, entity_id: str, *, max_depth: int = 1, max_nodes: int = 50
    ) -> NeighborResult:
        result = NeighborResult()
        target_entity = await self.get_entity(entity_id)
        if target_entity is None:
            return result

        result.entities.append(target_entity)
        result.depths[entity_id] = 0

        visited: set[str] = {entity_id}
        current_level = [entity_id]

        # 构建全局 name -> id 映射
        global_name_to_id: dict[str, str] = {}
        for kb_key_map in self._entity_key_to_id.values():
            for (n, _t), eid in kb_key_map.items():
                global_name_to_id.setdefault(n, eid)

        for depth in range(1, max_depth + 1):
            next_level: list[str] = []
            for rels in self._relations.values():
                for _rid, rel in rels.items():
                    source_id = global_name_to_id.get(rel.source_name, "")
                    target_id = global_name_to_id.get(rel.target_name, "")

                    if source_id in current_level and target_id not in visited:
                        entity = await self.get_entity(target_id)
                        if entity and len(result.entities) < max_nodes:
                            result.entities.append(entity)
                            result.relations.append(rel)
                            result.depths[target_id] = depth
                            visited.add(target_id)
                            next_level.append(target_id)
                    elif target_id in current_level and source_id not in visited:
                        entity = await self.get_entity(source_id)
                        if entity and len(result.entities) < max_nodes:
                            result.entities.append(entity)
                            result.relations.append(rel)
                            result.depths[source_id] = depth
                            visited.add(source_id)
                            next_level.append(source_id)
            current_level = next_level

        return result

    async def query_entities(
        self,
        kb_id: str,
        *,
        name_contains: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Entity], int]:
        all_entities = list(self._entities.get(kb_id, {}).values())
        filtered = all_entities
        if name_contains:
            filtered = [e for e in filtered if name_contains.lower() in e.name.lower()]
        if entity_type:
            filtered = [e for e in filtered if e.entity_type == entity_type]
        return filtered[offset : offset + limit], len(filtered)

    async def query_relations(
        self,
        kb_id: str,
        *,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Relation], int]:
        all_relations = list(self._relations.get(kb_id, {}).values())
        filtered = all_relations

        # 构建 id -> name 反向映射
        id_to_name: dict[str, str] = {}
        for eid, entity in self._entities.get(kb_id, {}).items():
            id_to_name[eid] = entity.name

        if source_entity_id:
            source_name = id_to_name.get(source_entity_id, "")
            if source_name:
                filtered = [r for r in filtered if r.source_name == source_name]
        if target_entity_id:
            target_name = id_to_name.get(target_entity_id, "")
            if target_name:
                filtered = [r for r in filtered if r.target_name == target_name]
        if relation_type:
            filtered = [r for r in filtered if r.relation_type == relation_type]
        return filtered[offset : offset + limit], len(filtered)

    async def query_communities(
        self,
        kb_id: str,
        *,
        level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Community], int]:
        all_communities = list(self._communities.get(kb_id, {}).values())
        filtered = all_communities
        if level is not None:
            filtered = [c for c in filtered if c.level == level]
        return filtered[offset : offset + limit], len(filtered)

    async def get_graph_data(self, kb_id: str, *, max_nodes: int = 200) -> GraphData:
        entities = list(self._entities.get(kb_id, {}).items())
        relations = list(self._relations.get(kb_id, {}).values())
        name_map = self._build_name_to_id_map(kb_id)

        # 限制节点数
        limited_entities = entities[:max_nodes]
        included_names = {e.name for _, e in limited_entities}

        nodes = [
            {"id": eid, "label": e.name, "type": e.entity_type}
            for eid, e in limited_entities
        ]

        edges = [
            {
                "source": name_map.get(r.source_name, r.source_name),
                "target": name_map.get(r.target_name, r.target_name),
                "type": r.relation_type,
                "weight": r.weight,
            }
            for r in relations
            if r.source_name in included_names and r.target_name in included_names
        ]

        return GraphData(nodes=nodes, edges=edges)

    async def delete_by_document(self, kb_id: str, document_id: str) -> int:
        entity_ids = self._entity_by_doc.get(kb_id, {}).get(document_id, set())
        count = 0
        for eid in list(entity_ids):
            entity = self._entities.get(kb_id, {}).pop(eid, None)
            if entity:
                self._entity_key_to_id.get(kb_id, {}).pop(
                    (entity.name, entity.entity_type), None
                )
                count += 1
        self._entity_by_doc.get(kb_id, {}).pop(document_id, None)
        return count

    async def delete_all(self, kb_id: str) -> int:
        count = (
            len(self._entities.pop(kb_id, {}))
            + len(self._relations.pop(kb_id, {}))
            + len(self._communities.pop(kb_id, {}))
        )
        self._entity_key_to_id.pop(kb_id, None)
        self._entity_by_doc.pop(kb_id, None)
        return count

    async def merge_entities(self, kb_id: str, entities: list[Entity]) -> dict[str, str]:
        name_to_id: dict[str, str] = {}

        # 按 (name, entity_type) 分组
        groups: dict[tuple[str, str], list[Entity]] = defaultdict(list)
        for entity in entities:
            groups[(entity.name, entity.entity_type)].append(entity)

        for (name, entity_type), group in groups.items():
            key = (name, entity_type)
            # 检查是否已存在同名同类型实体
            existing_id = self._entity_key_to_id[kb_id].get(key)
            existing_entity = self._entities[kb_id].get(existing_id) if existing_id else None

            if existing_entity is not None:
                # 合并到已有实体
                merged = self._merge_two_entities(existing_entity, group[0])
                for extra in group[1:]:
                    merged = self._merge_two_entities(merged, extra)
                self._entities[kb_id][existing_id] = merged
                name_to_id[name] = existing_id
            else:
                # 新建实体
                merged = group[0]
                for extra in group[1:]:
                    merged = self._merge_two_entities(merged, extra)
                eid = self._gen_id()
                self._entities[kb_id][eid] = merged
                self._entity_key_to_id[kb_id][key] = eid
                name_to_id[name] = eid

        return name_to_id

    async def entity_count(self, kb_id: str) -> int:
        return len(self._entities.get(kb_id, {}))

    async def relation_count(self, kb_id: str) -> int:
        return len(self._relations.get(kb_id, {}))

    async def community_count(self, kb_id: str) -> int:
        return len(self._communities.get(kb_id, {}))

    @staticmethod
    def _merge_two_entities(a: Entity, b: Entity) -> Entity:
        """合并两个同名同类型实体。"""
        # attributes 深度合并
        merged_attrs = {**a.attributes, **b.attributes}

        # confidence 取 max
        merged_confidence = max(a.confidence, b.confidence)

        # description 保留更长的
        merged_desc = a.description if len(a.description) >= len(b.description) else b.description

        # source_chunk 合并
        chunks: list[str] = []
        if a.source_chunk:
            chunks.append(a.source_chunk)
        if b.source_chunk:
            chunks.append(b.source_chunk)

        return Entity(
            name=a.name,
            entity_type=a.entity_type,
            description=merged_desc,
            attributes=merged_attrs,
            source_chunk="\n---\n".join(chunks) if chunks else "",
            confidence=merged_confidence,
            confidence_label=a.confidence_label,
            document_id=a.document_id or b.document_id,
        )
