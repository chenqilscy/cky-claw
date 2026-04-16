"""InMemoryGraphStore 测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.rag.graph.entity import (
    Community,
    ConfidenceLabel,
    Entity,
    Relation,
)
from ckyclaw_framework.rag.graph.store import InMemoryGraphStore


@pytest.fixture()
def store() -> InMemoryGraphStore:
    """空的内存图存储。"""
    return InMemoryGraphStore()


@pytest.fixture()
def sample_entities() -> list[Entity]:
    """示例实体列表。"""
    return [
        Entity(name="FastAPI", entity_type="Tool", description="Python web framework", confidence=0.9),
        Entity(name="Python", entity_type="Language", description="Programming language", confidence=0.95),
        Entity(name="React", entity_type="Tool", description="JavaScript UI library", confidence=0.9),
    ]


@pytest.fixture()
def sample_relations() -> list[Relation]:
    """示例关系列表。"""
    return [
        Relation(
            source_name="FastAPI", target_name="Python",
            relation_type="depends_on", description="FastAPI needs Python",
            weight=0.9, confidence=0.85,
        ),
    ]


class TestInMemoryGraphStoreEntities:
    """实体操作测试。"""

    async def test_add_and_get_entities(self, store: InMemoryGraphStore, sample_entities: list[Entity]) -> None:
        ids = await store.add_entities("kb-1", sample_entities, "doc-1")
        assert len(ids) == 3

        entity = await store.get_entity(ids[0])
        assert entity is not None
        assert entity.name == "FastAPI"

    async def test_entity_count(self, store: InMemoryGraphStore, sample_entities: list[Entity]) -> None:
        await store.add_entities("kb-1", sample_entities, "doc-1")
        assert await store.entity_count("kb-1") == 3
        assert await store.entity_count("kb-2") == 0

    async def test_query_entities_by_name(self, store: InMemoryGraphStore, sample_entities: list[Entity]) -> None:
        await store.add_entities("kb-1", sample_entities, "doc-1")

        results, total = await store.query_entities("kb-1", name_contains="fast")
        assert total == 1
        assert results[0].name == "FastAPI"

    async def test_query_entities_by_type(self, store: InMemoryGraphStore, sample_entities: list[Entity]) -> None:
        await store.add_entities("kb-1", sample_entities, "doc-1")

        results, total = await store.query_entities("kb-1", entity_type="Tool")
        assert total == 2

    async def test_query_entities_pagination(self, store: InMemoryGraphStore, sample_entities: list[Entity]) -> None:
        await store.add_entities("kb-1", sample_entities, "doc-1")

        results, total = await store.query_entities("kb-1", limit=2, offset=0)
        assert len(results) == 2
        assert total == 3


class TestInMemoryGraphStoreRelations:
    """关系操作测试。"""

    async def test_add_relations(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description="Entity A"),
            Entity(name="B", entity_type="Concept", description="Entity B"),
        ]
        ids = await store.add_entities("kb-1", entities, "doc-1")
        name_to_id = {"A": ids[0], "B": ids[1]}

        rels = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
        ]
        rids = await store.add_relations("kb-1", rels, name_to_id)
        assert len(rids) == 1

    async def test_relation_count(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description=""),
            Entity(name="B", entity_type="Concept", description=""),
        ]
        ids = await store.add_entities("kb-1", entities, "doc-1")
        name_to_id = {"A": ids[0], "B": ids[1]}

        rels = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
        ]
        await store.add_relations("kb-1", rels, name_to_id)
        assert await store.relation_count("kb-1") == 1


class TestInMemoryGraphStoreNeighbors:
    """邻居遍历测试。"""

    async def test_get_neighbors_depth1(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description=""),
            Entity(name="B", entity_type="Concept", description=""),
            Entity(name="C", entity_type="Concept", description=""),
        ]
        ids = await store.add_entities("kb-1", entities, "doc-1")
        name_to_id = {e.name: eid for e, eid in zip(entities, ids)}

        rels = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
            Relation(source_name="B", target_name="C", relation_type="uses", description=""),
        ]
        await store.add_relations("kb-1", rels, name_to_id)

        result = await store.get_neighbors(ids[0], max_depth=1)
        assert len(result.entities) == 2  # A + B
        assert len(result.relations) == 1

    async def test_get_neighbors_depth2(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description=""),
            Entity(name="B", entity_type="Concept", description=""),
            Entity(name="C", entity_type="Concept", description=""),
        ]
        ids = await store.add_entities("kb-1", entities, "doc-1")
        name_to_id = {e.name: eid for e, eid in zip(entities, ids)}

        rels = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
            Relation(source_name="B", target_name="C", relation_type="uses", description=""),
        ]
        await store.add_relations("kb-1", rels, name_to_id)

        result = await store.get_neighbors(ids[0], max_depth=2)
        assert len(result.entities) == 3  # A + B + C
        assert len(result.relations) == 2

    async def test_get_neighbors_nonexistent(self, store: InMemoryGraphStore) -> None:
        result = await store.get_neighbors("nonexistent")
        assert len(result.entities) == 0


class TestInMemoryGraphStoreCommunities:
    """社区操作测试。"""

    async def test_add_and_query_communities(self, store: InMemoryGraphStore) -> None:
        communities = [
            Community(name="Web", summary="Web development tools", entity_names=["FastAPI", "React"]),
            Community(name="Backend", summary="Backend frameworks", entity_names=["FastAPI"]),
        ]
        await store.add_communities("kb-1", communities)
        assert await store.community_count("kb-1") == 2

        results, total = await store.query_communities("kb-1")
        assert total == 2

    async def test_query_communities_by_level(self, store: InMemoryGraphStore) -> None:
        communities = [
            Community(name="Web", summary="", entity_names=[], level=0),
            Community(name="All", summary="", entity_names=[], level=1),
        ]
        await store.add_communities("kb-1", communities)

        results, total = await store.query_communities("kb-1", level=0)
        assert total == 1
        assert results[0].name == "Web"


class TestInMemoryGraphStoreDelete:
    """删除操作测试。"""

    async def test_delete_by_document(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description=""),
            Entity(name="B", entity_type="Concept", description=""),
        ]
        await store.add_entities("kb-1", entities[:1], "doc-1")
        await store.add_entities("kb-1", entities[1:], "doc-2")

        count = await store.delete_by_document("kb-1", "doc-1")
        assert count == 1
        assert await store.entity_count("kb-1") == 1

    async def test_delete_all(self, store: InMemoryGraphStore) -> None:
        entities = [Entity(name="A", entity_type="Concept", description="")]
        await store.add_entities("kb-1", entities, "doc-1")

        count = await store.delete_all("kb-1")
        assert count >= 1
        assert await store.entity_count("kb-1") == 0


class TestInMemoryGraphStoreMerge:
    """实体合并测试。"""

    async def test_merge_same_name_same_type(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="Python", entity_type="Language", description="A language", confidence=0.8,
                   attributes={"version": "3.12"}),
            Entity(name="Python", entity_type="Language", description="Python programming language with rich ecosystem",
                   confidence=0.95, attributes={"typing": "dynamic"}),
        ]

        name_to_id = await store.merge_entities("kb-1", entities)

        assert await store.entity_count("kb-1") == 1
        assert "Python" in name_to_id

        merged = await store.get_entity(name_to_id["Python"])
        assert merged is not None
        assert merged.confidence == 0.95  # 取 max
        assert "Python programming language" in merged.description  # 保留更长的
        assert merged.attributes.get("typing") == "dynamic"  # 深度合并
        assert merged.attributes.get("version") == "3.12"

    async def test_merge_different_type_keeps_separate(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="Python", entity_type="Language", description="Programming language"),
            Entity(name="Python", entity_type="Tool", description="Python interpreter"),
        ]

        name_to_id = await store.merge_entities("kb-1", entities)

        assert await store.entity_count("kb-1") == 2


class TestInMemoryGraphStoreGraphData:
    """图谱可视化数据测试。"""

    async def test_get_graph_data(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description=""),
            Entity(name="B", entity_type="Concept", description=""),
        ]
        ids = await store.add_entities("kb-1", entities, "doc-1")
        name_to_id = {"A": ids[0], "B": ids[1]}

        rels = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
        ]
        await store.add_relations("kb-1", rels, name_to_id)

        data = await store.get_graph_data("kb-1")
        assert len(data.nodes) == 2
        assert len(data.edges) == 1
        assert data.edges[0]["type"] == "uses"

    async def test_get_graph_data_max_nodes(self, store: InMemoryGraphStore) -> None:
        entities = [
            Entity(name=f"E{i}", entity_type="Concept", description="") for i in range(10)
        ]
        await store.add_entities("kb-1", entities, "doc-1")

        data = await store.get_graph_data("kb-1", max_nodes=5)
        assert len(data.nodes) == 5
