"""VectorStore — 向量存储抽象与实现。"""

from __future__ import annotations

import asyncio
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """向量搜索结果。

    Attributes:
        content: 文本内容。
        score: 相似度分数（越高越相似）。
        metadata: 附加元数据。
    """

    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    async def add(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """添加向量化文本。

        Args:
            texts: 文本列表。
            embeddings: 对应的向量列表。
            metadatas: 可选元数据列表。
            ids: 可选 ID 列表，不提供则自动生成。

        Returns:
            存储后的 ID 列表。
        """
        ...

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """基于向量相似度搜索。

        Args:
            query_embedding: 查询向量。
            top_k: 返回结果数量上限。
            filter_metadata: 元数据过滤条件（精确匹配）。

        Returns:
            按相似度降序排列的搜索结果。
        """
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> int:
        """删除指定 ID 的向量记录。

        Args:
            ids: 待删除的 ID 列表。

        Returns:
            实际删除的记录数。
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """返回存储中的向量记录总数。"""
        ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    if len(a) != len(b):
        raise ValueError(f"向量维度不一致: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class _VectorRecord:
    """内存向量记录。"""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


class InMemoryVectorStore(VectorStore):
    """内存向量存储——仅用于测试和小规模场景。"""

    def __init__(self) -> None:
        self._records: dict[str, _VectorRecord] = {}
        self._counter = 0
        self._lock = asyncio.Lock()

    async def add(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """添加记录到内存。"""
        if len(texts) != len(embeddings):
            raise ValueError("texts 和 embeddings 长度必须一致")
        if metadatas is not None and len(metadatas) != len(texts):
            raise ValueError("metadatas 长度必须与 texts 一致")
        if ids is not None and len(ids) != len(texts):
            raise ValueError("ids 长度必须与 texts 一致")

        result_ids: list[str] = []
        async with self._lock:
            for i, (text, emb) in enumerate(zip(texts, embeddings)):
                record_id = ids[i] if ids else f"vec_{self._counter}"
                self._counter += 1
                meta = metadatas[i] if metadatas else {}
                self._records[record_id] = _VectorRecord(
                    id=record_id,
                    text=text,
                    embedding=emb,
                    metadata=meta,
                )
                result_ids.append(record_id)
        return result_ids

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """暴力搜索，计算余弦相似度。"""
        async with self._lock:
            candidates = list(self._records.values())

        # 元数据过滤
        if filter_metadata:
            candidates = [
                r for r in candidates
                if all(r.metadata.get(k) == v for k, v in filter_metadata.items())
            ]

        # 计算相似度
        scored: list[tuple[float, _VectorRecord]] = []
        for record in candidates:
            score = cosine_similarity(query_embedding, record.embedding)
            scored.append((score, record))

        # 按分数降序排列
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                content=record.text,
                score=score,
                metadata=record.metadata,
            )
            for score, record in scored[:top_k]
        ]

    async def delete(self, ids: list[str]) -> int:
        """删除指定记录。"""
        count = 0
        async with self._lock:
            for record_id in ids:
                if record_id in self._records:
                    del self._records[record_id]
                    count += 1
        return count

    async def count(self) -> int:
        """返回记录总数。"""
        async with self._lock:
            return len(self._records)
