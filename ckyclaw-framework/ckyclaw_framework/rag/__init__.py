"""CkyClaw RAG — 检索增强生成模块。

提供文档加载、分块、Embedding、向量存储和 RAG Pipeline 全套能力，
使 Agent 可基于知识库进行检索增强对话。
"""

from ckyclaw_framework.rag.chunker import (
    Chunk,
    ChunkStrategy,
    FixedSizeChunker,
    MarkdownChunker,
    RecursiveCharacterChunker,
)
from ckyclaw_framework.rag.document import Document, DocumentLoader, TextLoader
from ckyclaw_framework.rag.embedding import EmbeddingProvider, InMemoryEmbeddingProvider
from ckyclaw_framework.rag.pipeline import RAGPipeline, RAGResult
from ckyclaw_framework.rag.tool import create_knowledge_base_tool
from ckyclaw_framework.rag.vector_store import (
    InMemoryVectorStore,
    SearchResult,
    VectorStore,
)

__all__ = [
    # Document
    "Document",
    "DocumentLoader",
    "TextLoader",
    # Chunker
    "Chunk",
    "ChunkStrategy",
    "FixedSizeChunker",
    "MarkdownChunker",
    "RecursiveCharacterChunker",
    # Embedding
    "EmbeddingProvider",
    "InMemoryEmbeddingProvider",
    # Vector Store
    "VectorStore",
    "InMemoryVectorStore",
    "SearchResult",
    # Pipeline
    "RAGPipeline",
    "RAGResult",
    # Tool
    "create_knowledge_base_tool",
]
