"""Document — 文档加载与表示。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """一份文档的内部表示。

    Attributes:
        content: 文档文本内容。
        metadata: 附加元数据（文件名、来源 URL、页码等）。
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentLoader(ABC):
    """文档加载器抽象基类。"""

    @abstractmethod
    async def load(self, source: str) -> list[Document]:
        """从给定源加载文档。

        Args:
            source: 文件路径、URL 或其他资源标识符。

        Returns:
            加载到的文档列表。
        """
        ...


class TextLoader(DocumentLoader):
    """纯文本 / Markdown 文件加载器。"""

    def __init__(self, encoding: str = "utf-8") -> None:
        self._encoding = encoding

    async def load(self, source: str) -> list[Document]:
        """读取文本文件，返回单个 Document。

        Args:
            source: 文件路径。

        Returns:
            包含文件内容的 Document 列表。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        import asyncio
        from pathlib import Path

        path = Path(source)
        content = await asyncio.to_thread(path.read_text, encoding=self._encoding)
        return [Document(content=content, metadata={"source": source})]
