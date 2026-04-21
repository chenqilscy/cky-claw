"""Kasaya RAG — 检索增强生成模块。

提供文档加载、分块、Embedding、向量存储和 RAG Pipeline 全套能力，
使 Agent 可基于知识库进行检索增强对话。
"""

from kasaya.rag.chunker import (
    Chunk,
    ChunkStrategy,
    FixedSizeChunker,
    MarkdownChunker,
    RecursiveCharacterChunker,
)
from kasaya.rag.document import Document, DocumentLoader, TextLoader
from kasaya.rag.embedding import EmbeddingProvider, InMemoryEmbeddingProvider
from kasaya.rag.graph.community import CommunityDetector
from kasaya.rag.graph.entity import (
    Community,
    ConfidenceLabel,
    Entity,
    ExtractionResult,
    Relation,
)
from kasaya.rag.graph.extractor import GraphExtractor, LLMGraphExtractor
from kasaya.rag.graph.retriever import GraphRetriever, RetrievalResult
from kasaya.rag.graph.store import (
    GraphData,
    GraphStore,
    InMemoryGraphStore,
    NeighborResult,
)
from kasaya.rag.pipeline import RAGPipeline, RAGResult
from kasaya.rag.tool import (
    create_knowledge_base_tool,
    create_knowledge_graph_tool,
)
from kasaya.rag.vector_store import (
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
    "create_knowledge_graph_tool",
    # Graph
    "Community",
    "CommunityDetector",
    "ConfidenceLabel",
    "Entity",
    "ExtractionResult",
    "Relation",
    "GraphExtractor",
    "LLMGraphExtractor",
    "GraphRetriever",
    "RetrievalResult",
    "GraphStore",
    "InMemoryGraphStore",
    "GraphData",
    "NeighborResult",
]
