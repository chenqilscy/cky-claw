"""LLMGraphExtractor 测试。"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from kasaya.model.provider import ModelResponse
from kasaya.rag.graph.entity import ConfidenceLabel
from kasaya.rag.graph.extractor import LLMGraphExtractor


def _make_mock_provider(response_content: str) -> AsyncMock:
    """构造 mock ModelProvider，返回指定内容。"""
    mock_provider = AsyncMock()
    mock_provider.chat.return_value = ModelResponse(content=response_content)
    return mock_provider


@pytest.fixture()
def sample_response() -> str:
    """标准抽取结果 JSON。"""
    return json.dumps({
        "entities": [
            {
                "name": "FastAPI",
                "type": "Tool",
                "description": "Python web framework for building APIs",
                "confidence": 0.95,
                "attributes": {"language": "Python"},
            },
            {
                "name": "Python",
                "type": "Language",
                "description": "A general-purpose programming language",
                "confidence": 0.9,
                "attributes": {},
            },
        ],
        "relations": [
            {
                "source": "FastAPI",
                "target": "Python",
                "type": "depends_on",
                "description": "FastAPI is built on Python",
                "confidence": 0.85,
                "weight": 0.9,
            },
        ],
    })


class TestLLMGraphExtractor:
    """LLMGraphExtractor 测试。"""

    async def test_extract_basic(self, sample_response: str) -> None:
        """基本抽取测试。"""
        provider = _make_mock_provider(sample_response)
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "FastAPI is a Python web framework.",
            model_provider=provider,
            model="test-model",
        )

        assert len(result.entities) == 2
        assert result.entities[0].name == "FastAPI"
        assert result.entities[0].entity_type == "Tool"
        assert result.entities[0].confidence == 0.95
        assert result.entities[0].confidence_label == ConfidenceLabel.EXTRACTED

        assert len(result.relations) == 1
        assert result.relations[0].source_name == "FastAPI"
        assert result.relations[0].target_name == "Python"
        assert result.relations[0].confidence_label == ConfidenceLabel.INFERRED

        assert result.content_hash != ""
        assert provider.chat.called

    async def test_extract_with_entity_types(self, sample_response: str) -> None:
        """带实体类型约束的抽取。"""
        provider = _make_mock_provider(sample_response)
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "Some text",
            entity_types=["Tool", "Language"],
            model_provider=provider,
            model="test-model",
        )

        # 验证 system prompt 中包含实体类型
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][1]
        system_msg = messages[0]
        assert "Tool" in system_msg.content
        assert "Language" in system_msg.content

    async def test_extract_invalid_json(self) -> None:
        """LLM 返回非 JSON 内容时的处理。"""
        provider = _make_mock_provider("This is not JSON")
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "Some text",
            model_provider=provider,
            model="test-model",
        )

        assert result.entities == []
        assert result.relations == []

    async def test_extract_empty_entities(self) -> None:
        """空实体列表。"""
        provider = _make_mock_provider(json.dumps({"entities": [], "relations": []}))
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "Some text",
            model_provider=provider,
            model="test-model",
        )

        assert result.entities == []
        assert result.relations == []

    async def test_extract_missing_name_skipped(self) -> None:
        """缺少 name 的实体被跳过。"""
        provider = _make_mock_provider(json.dumps({
            "entities": [
                {"type": "Tool", "description": "No name entity"},
            ],
            "relations": [],
        }))
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "Some text",
            model_provider=provider,
            model="test-model",
        )

        assert result.entities == []

    async def test_extract_low_confidence_ambiguous(self) -> None:
        """低置信度标记为 AMBIGUOUS。"""
        provider = _make_mock_provider(json.dumps({
            "entities": [
                {
                    "name": "MaybeEntity",
                    "type": "Concept",
                    "description": "Uncertain",
                    "confidence": 0.3,
                },
            ],
            "relations": [],
        }))
        extractor = LLMGraphExtractor()

        result = await extractor.extract(
            "Some text",
            model_provider=provider,
            model="test-model",
        )

        assert len(result.entities) == 1
        assert result.entities[0].confidence_label == ConfidenceLabel.AMBIGUOUS

    async def test_extract_custom_system_prompt(self, sample_response: str) -> None:
        """自定义系统 prompt。"""
        provider = _make_mock_provider(sample_response)
        extractor = LLMGraphExtractor(system_prompt="Custom prompt for extraction.")

        await extractor.extract(
            "Some text",
            model_provider=provider,
            model="test-model",
        )

        call_args = provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][1]
        assert messages[0].content == "Custom prompt for extraction."

    async def test_content_hash_deterministic(self, sample_response: str) -> None:
        """相同输入产生相同 content_hash。"""
        provider1 = _make_mock_provider(sample_response)
        provider2 = _make_mock_provider(sample_response)
        extractor = LLMGraphExtractor()

        result1 = await extractor.extract("Same text", model_provider=provider1, model="m")
        result2 = await extractor.extract("Same text", model_provider=provider2, model="m")

        assert result1.content_hash == result2.content_hash

    async def test_extract_response_format_passed(self, sample_response: str) -> None:
        """验证 response_format=json_object 被传入。"""
        provider = _make_mock_provider(sample_response)
        extractor = LLMGraphExtractor()

        await extractor.extract("Text", model_provider=provider, model="m")

        call_kwargs = provider.chat.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}
