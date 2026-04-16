"""知识图谱核心数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConfidenceLabel(StrEnum):
    """关系/实体的置信度标签，借鉴 graphify 的三级标注体系。"""

    EXTRACTED = "extracted"  # 直接从文本中抽取，高置信度
    INFERRED = "inferred"  # 推理得出，中等置信度
    AMBIGUOUS = "ambiguous"  # 不确定，需人工审查


@dataclass
class Entity:
    """图谱实体。"""

    name: str
    entity_type: str  # Person / Concept / Tool / API / Organization / Event / ...
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    source_chunk: str = ""
    confidence: float = 1.0
    confidence_label: ConfidenceLabel = ConfidenceLabel.EXTRACTED
    document_id: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be in [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)


@dataclass
class Relation:
    """实体间关系。"""

    source_name: str  # 源实体 name（抽取阶段用 name 引用，持久化时解析为 UUID）
    target_name: str
    relation_type: str  # uses / depends_on / part_of / related_to / ...
    description: str
    weight: float = 1.0
    source_chunk: str = ""
    confidence: float = 1.0
    confidence_label: ConfidenceLabel = ConfidenceLabel.INFERRED

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be in [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)
        if not 0.0 <= self.weight <= 1.0:
            msg = f"weight must be in [0.0, 1.0], got {self.weight}"
            raise ValueError(msg)


@dataclass
class Community:
    """图社区（Leiden 检测产出）。"""

    name: str
    summary: str  # Wiki 式摘要（LLM 生成）
    entity_names: list[str] = field(default_factory=list)
    level: int = 0  # 0 = 最细粒度
    parent_id: str | None = None


@dataclass
class ExtractionResult:
    """单次抽取的结果。"""

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    source_document_id: str = ""
    source_chunk_index: int = 0
    content_hash: str = ""  # SHA256 of input chunk, for incremental update


def classify_confidence(confidence: float) -> ConfidenceLabel:
    """根据置信度分数自动分类标签。"""
    if confidence >= 0.9:
        return ConfidenceLabel.EXTRACTED
    if confidence >= 0.5:
        return ConfidenceLabel.INFERRED
    return ConfidenceLabel.AMBIGUOUS
