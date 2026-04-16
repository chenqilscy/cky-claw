"""GraphExtractor — 使用 LLM 从文本中抽取实体和关系。"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.rag.graph.entity import (
    Community,
    ConfidenceLabel,
    Entity,
    ExtractionResult,
    Relation,
    classify_confidence,
)

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message, MessageRole
    from ckyclaw_framework.model.provider import ModelProvider
    from ckyclaw_framework.model.settings import ModelSettings

logger = logging.getLogger(__name__)

# 默认抽取 prompt 模板
_DEFAULT_SYSTEM_PROMPT = """\
你是一个知识图谱抽取专家。从以下文本中抽取实体和关系。
返回严格的 JSON 格式，不要包含任何其他内容。

输出格式：
{
  "entities": [
    {
      "name": "实体名称",
      "type": "实体类型（Person/Concept/Tool/API/Organization/Event/...）",
      "description": "对该实体的简要描述",
      "confidence": 0.9,
      "attributes": {}
    }
  ],
  "relations": [
    {
      "source": "源实体名称",
      "target": "目标实体名称",
      "type": "关系类型（uses/depends_on/part_of/related_to/...）",
      "description": "对该关系的简要描述",
      "confidence": 0.8,
      "weight": 0.8
    }
  ]
}

置信度标注规则：
- confidence >= 0.9：文本中直接出现该实体/关系的明确表述
- 0.5 <= confidence < 0.9：基于文本内容合理推理得出
- confidence < 0.5：不确定，可能存在但不明确
"""

_DEFAULT_ENTITY_TYPES_HINT = "\n\n需要关注的实体类型：{entity_types}"

_DEFAULT_USER_PROMPT_TEMPLATE = """\
以下是需要抽取的文本内容：

---
{text}
---

请从中抽取实体和关系，返回 JSON 格式。"""


class GraphExtractor(ABC):
    """图谱抽取器抽象基类。"""

    @abstractmethod
    async def extract(
        self,
        text: str,
        *,
        chunk_index: int = 0,
        document_id: str = "",
        entity_types: list[str] | None = None,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> ExtractionResult:
        """从文本中抽取实体和关系。"""
        ...


class LLMGraphExtractor(GraphExtractor):
    """使用 LLM 从文本中抽取实体和关系。

    调用 ModelProvider.chat() + response_format={"type":"json_object"}
    强制 LLM 输出可解析的 JSON。

    Args:
        system_prompt: 自定义系统 prompt，覆盖默认模板。
    """

    def __init__(self, system_prompt: str | None = None) -> None:
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    async def extract(
        self,
        text: str,
        *,
        chunk_index: int = 0,
        document_id: str = "",
        entity_types: list[str] | None = None,
        model_provider: ModelProvider,
        model: str,
        settings: ModelSettings | None = None,
    ) -> ExtractionResult:
        """从文本中抽取实体和关系。"""
        from ckyclaw_framework.model.message import Message, MessageRole  # noqa: F811

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # 构建系统 prompt
        system_text = self._system_prompt
        if entity_types:
            system_text += _DEFAULT_ENTITY_TYPES_HINT.format(entity_types=", ".join(entity_types))

        # 构建消息
        messages: list[Message] = [
            Message(role=MessageRole.SYSTEM, content=system_text),
            Message(role=MessageRole.USER, content=_DEFAULT_USER_PROMPT_TEMPLATE.format(text=text)),
        ]

        # 调用 LLM
        response = await model_provider.chat(
            model=model,
            messages=messages,
            settings=settings,
            response_format={"type": "json_object"},
        )

        # 解析响应
        raw_content = response.content or "{}"
        entities, relations = self._parse_response(raw_content)

        # 应用置信度分类
        for entity in entities:
            entity.confidence_label = classify_confidence(entity.confidence)
            entity.document_id = document_id
        for relation in relations:
            relation.confidence_label = classify_confidence(relation.confidence)

        return ExtractionResult(
            entities=entities,
            relations=relations,
            source_document_id=document_id,
            source_chunk_index=chunk_index,
            content_hash=content_hash,
        )

    def _parse_response(self, raw: str) -> tuple[list[Entity], list[Relation]]:
        """解析 LLM JSON 响应为 Entity + Relation 列表。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM 返回非 JSON 内容，跳过解析: %s", raw[:200])
            return [], []

        if not isinstance(data, dict):
            logger.warning("LLM 返回非 dict JSON，跳过解析")
            return [], []

        entities: list[Entity] = []
        for item in data.get("entities", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue
            try:
                entities.append(
                    Entity(
                        name=name,
                        entity_type=item.get("type", "Concept"),
                        description=item.get("description", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        attributes=item.get("attributes", {}),
                    )
                )
            except (ValueError, TypeError) as e:
                logger.debug("跳过无效实体 %s: %s", name, e)
                continue

        relations: list[Relation] = []
        for item in data.get("relations", []):
            if not isinstance(item, dict):
                continue
            source = item.get("source", "").strip()
            target = item.get("target", "").strip()
            if not source or not target:
                continue
            try:
                relations.append(
                    Relation(
                        source_name=source,
                        target_name=target,
                        relation_type=item.get("type", "related_to"),
                        description=item.get("description", ""),
                        weight=float(item.get("weight", 0.7)),
                        confidence=float(item.get("confidence", 0.5)),
                    )
                )
            except (ValueError, TypeError) as e:
                logger.debug("跳过无效关系 %s->%s: %s", source, target, e)
                continue

        return entities, relations
