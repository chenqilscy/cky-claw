"""EmbeddingProvider — Embedding 向量化抽象。"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Embedding 模型提供商抽象。

    支持单条和批量嵌入，由具体实现对接不同厂商（OpenAI / 通义 / 文心等）。
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本批量转为向量。

        Args:
            texts: 待嵌入的文本列表。

        Returns:
            与 texts 等长的向量列表，每个向量为 float 列表。
        """
        ...

    async def embed_single(self, text: str) -> list[float]:
        """嵌入单条文本（便捷方法）。"""
        results = await self.embed([text])
        return results[0]

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度。"""
        ...


class InMemoryEmbeddingProvider(EmbeddingProvider):
    """基于哈希的伪 Embedding，仅用于测试。

    生成确定性的固定维度向量（非语义，仅保证相同文本得到相同向量）。
    """

    def __init__(self, dimension: int = 128) -> None:
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """生成伪向量。"""
        return [self._hash_embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_embed(self, text: str) -> list[float]:
        """用 SHA-256 展开为固定维度浮点向量。"""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # 循环扩展到目标维度
        raw: list[int] = []
        while len(raw) < self._dimension:
            raw.extend(digest)
        # 归一化到 [-1, 1]
        vector = [(b / 127.5 - 1.0) for b in raw[:self._dimension]]
        # L2 归一化
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    """基于 LiteLLM 的 Embedding 提供商，支持 10+ 厂商。

    Requires:
        pip install litellm
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._api_key = api_key
        self._api_base = api_base
        self._kwargs = kwargs

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """通过 LiteLLM 调用 Embedding API。"""
        try:
            import litellm
        except ImportError as e:
            raise ImportError(
                "LiteLLMEmbeddingProvider 需要 litellm 包。"
                "请运行: pip install litellm"
            ) from e

        response = await litellm.aembedding(
            model=self._model,
            input=texts,
            api_key=self._api_key,
            api_base=self._api_base,
            **self._kwargs,
        )
        return [item["embedding"] for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension
