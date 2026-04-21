"""知识图谱数据类测试。"""

from __future__ import annotations

import pytest

from kasaya.rag.graph.entity import (
    Community,
    ConfidenceLabel,
    Entity,
    ExtractionResult,
    Relation,
    classify_confidence,
)


class TestConfidenceLabel:
    """置信度分类测试。"""

    def test_extracted_high_confidence(self) -> None:
        assert classify_confidence(0.9) == ConfidenceLabel.EXTRACTED
        assert classify_confidence(1.0) == ConfidenceLabel.EXTRACTED
        assert classify_confidence(0.95) == ConfidenceLabel.EXTRACTED

    def test_inferred_medium_confidence(self) -> None:
        assert classify_confidence(0.5) == ConfidenceLabel.INFERRED
        assert classify_confidence(0.7) == ConfidenceLabel.INFERRED
        assert classify_confidence(0.89) == ConfidenceLabel.INFERRED

    def test_ambiguous_low_confidence(self) -> None:
        assert classify_confidence(0.0) == ConfidenceLabel.AMBIGUOUS
        assert classify_confidence(0.1) == ConfidenceLabel.AMBIGUOUS
        assert classify_confidence(0.49) == ConfidenceLabel.AMBIGUOUS


class TestEntity:
    """Entity 数据类测试。"""

    def test_create_entity(self) -> None:
        entity = Entity(
            name="Python",
            entity_type="Tool",
            description="A programming language",
            confidence=0.95,
        )
        assert entity.name == "Python"
        assert entity.entity_type == "Tool"
        assert entity.confidence == 0.95
        assert entity.confidence_label == ConfidenceLabel.EXTRACTED
        assert entity.attributes == {}
        assert entity.document_id == ""

    def test_entity_confidence_validation(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            Entity(name="X", entity_type="Concept", description="", confidence=1.5)
        with pytest.raises(ValueError, match="confidence"):
            Entity(name="X", entity_type="Concept", description="", confidence=-0.1)

    def test_entity_with_attributes(self) -> None:
        entity = Entity(
            name="FastAPI",
            entity_type="Tool",
            description="Python web framework",
            attributes={"version": "0.115", "language": "Python"},
            confidence=0.9,
        )
        assert entity.attributes["version"] == "0.115"


class TestRelation:
    """Relation 数据类测试。"""

    def test_create_relation(self) -> None:
        rel = Relation(
            source_name="FastAPI",
            target_name="Python",
            relation_type="depends_on",
            description="FastAPI depends on Python",
            weight=0.9,
            confidence=0.85,
        )
        assert rel.source_name == "FastAPI"
        assert rel.target_name == "Python"
        assert rel.relation_type == "depends_on"
        assert rel.confidence_label == ConfidenceLabel.INFERRED

    def test_relation_confidence_validation(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            Relation(
                source_name="A", target_name="B", relation_type="uses",
                description="", confidence=2.0,
            )

    def test_relation_weight_validation(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            Relation(
                source_name="A", target_name="B", relation_type="uses",
                description="", weight=1.5,
            )


class TestCommunity:
    """Community 数据类测试。"""

    def test_create_community(self) -> None:
        community = Community(
            name="Web 框架",
            summary="与 Web 开发相关的工具和概念",
            entity_names=["FastAPI", "React", "Django"],
            level=0,
        )
        assert community.name == "Web 框架"
        assert len(community.entity_names) == 3
        assert community.parent_id is None


class TestExtractionResult:
    """ExtractionResult 数据类测试。"""

    def test_create_extraction_result(self) -> None:
        entities = [
            Entity(name="A", entity_type="Concept", description="Entity A"),
        ]
        relations = [
            Relation(source_name="A", target_name="B", relation_type="uses", description=""),
        ]
        result = ExtractionResult(
            entities=entities,
            relations=relations,
            source_document_id="doc-1",
            source_chunk_index=0,
            content_hash="abc123",
        )
        assert len(result.entities) == 1
        assert len(result.relations) == 1
        assert result.content_hash == "abc123"

    def test_empty_result(self) -> None:
        result = ExtractionResult()
        assert result.entities == []
        assert result.relations == []
        assert result.content_hash == ""
