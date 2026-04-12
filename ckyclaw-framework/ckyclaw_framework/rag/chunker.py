"""Chunker — 文档分块策略。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ckyclaw_framework.rag.document import Document


@dataclass
class Chunk:
    """文档分块。

    Attributes:
        content: 分块文本。
        metadata: 继承自 Document 的元数据 + 块级元数据（index / start_char 等）。
        document_id: 所属文档标识（由上层赋值）。
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str = ""


class ChunkStrategy(ABC):
    """分块策略抽象基类。"""

    @abstractmethod
    def split(self, document: Document) -> list[Chunk]:
        """将文档拆分为多个 Chunk。

        Args:
            document: 待分块的文档。

        Returns:
            分块列表。
        """
        ...


class FixedSizeChunker(ChunkStrategy):
    """固定大小分块，带可选重叠。"""

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能为负数")
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split(self, document: Document) -> list[Chunk]:
        """按固定大小切分文本。"""
        text = document.content
        if not text:
            return []

        chunks: list[Chunk] = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + self._chunk_size
            chunk_text = text[start:end]
            if chunk_text.strip():  # 跳过纯空白块
                chunks.append(Chunk(
                    content=chunk_text,
                    metadata={**document.metadata, "chunk_index": idx, "start_char": start},
                ))
                idx += 1
            start = end - self._overlap if end < len(text) else end
        return chunks


class RecursiveCharacterChunker(ChunkStrategy):
    """递归字符分块：优先按段落 → 换行 → 句号 → 空格 → 字符切分。"""

    DEFAULT_SEPARATORS = ["\n\n", "\n", "。", ".", " "]

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        separators: list[str] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能为负数")
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._separators = separators or self.DEFAULT_SEPARATORS

    def split(self, document: Document) -> list[Chunk]:
        """递归切分文档。"""
        pieces = self._recursive_split(document.content, self._separators)
        # 合并小片段
        merged = self._merge_pieces(pieces)
        chunks: list[Chunk] = []
        for idx, text in enumerate(merged):
            if text.strip():
                chunks.append(Chunk(
                    content=text,
                    metadata={**document.metadata, "chunk_index": idx},
                ))
        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """递归尝试分隔符。"""
        if len(text) <= self._chunk_size:
            return [text]

        for sep in separators:
            parts = text.split(sep)
            if len(parts) > 1:
                result: list[str] = []
                for part in parts:
                    if len(part) <= self._chunk_size:
                        result.append(part)
                    else:
                        remaining_seps = separators[separators.index(sep) + 1:]
                        result.extend(self._recursive_split(part, remaining_seps))
                return result

        # 所有分隔符都无法切分，退化为固定大小
        result = []
        start = 0
        while start < len(text):
            result.append(text[start:start + self._chunk_size])
            start += self._chunk_size
        return result

    def _merge_pieces(self, pieces: list[str]) -> list[str]:
        """将过小的片段合并到 chunk_size 以内。"""
        merged: list[str] = []
        current = ""
        for piece in pieces:
            candidate = current + piece
            if len(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                current = piece
        if current:
            merged.append(current)
        return merged


class MarkdownChunker(ChunkStrategy):
    """Markdown 感知分块：按标题层级切分，保留标题上下文。"""

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, chunk_size: int = 1024) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        self._chunk_size = chunk_size

    def split(self, document: Document) -> list[Chunk]:
        """按 Markdown 标题切分。"""
        text = document.content
        if not text:
            return []

        # 找到所有标题位置
        headings = list(self._HEADING_RE.finditer(text))
        if not headings:
            # 无标题，退化为单块或固定大小
            return [Chunk(content=text, metadata={**document.metadata, "chunk_index": 0})]

        chunks: list[Chunk] = []
        for i, match in enumerate(headings):
            start = match.start()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            section = text[start:end].strip()
            if section:
                heading_text = match.group(2).strip()
                chunks.append(Chunk(
                    content=section,
                    metadata={
                        **document.metadata,
                        "chunk_index": i,
                        "heading": heading_text,
                        "heading_level": len(match.group(1)),
                    },
                ))

        # 标题之前的内容
        if headings and headings[0].start() > 0:
            preamble = text[:headings[0].start()].strip()
            if preamble:
                chunks.insert(0, Chunk(
                    content=preamble,
                    metadata={**document.metadata, "chunk_index": -1, "heading": "_preamble"},
                ))

        return chunks
