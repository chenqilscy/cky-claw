"""RAGPipeline — 检索增强生成管线。"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kasaya.rag.chunker import Chunk, ChunkStrategy

if TYPE_CHECKING:
    from kasaya.rag.document import Document, DocumentLoader
    from kasaya.rag.embedding import EmbeddingProvider
    from kasaya.rag.vector_store import SearchResult, VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """RAG 检索结果。

    Attributes:
        query: 原始查询。
        results: 检索到的相关片段。
        augmented_prompt: 带检索上下文的增强 Prompt。
    """

    query: str
    results: list[SearchResult]
    augmented_prompt: str


class RAGPipeline:
    """检索增强生成管线。

    完整流程：加载文档 → 分块 → Embedding → 存入向量库 → 检索 → 增强 Prompt。

    用法::

        pipeline = RAGPipeline(
            embedding_provider=embedding,
            vector_store=store,
            chunk_strategy=FixedSizeChunker(512, 64),
        )
        # 索引文档
        await pipeline.ingest_documents(documents)
        # 检索增强
        result = await pipeline.retrieve("用户问题", top_k=5)
        print(result.augmented_prompt)
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        chunk_strategy: ChunkStrategy | None = None,
        prompt_template: str = (
            "请基于以下参考资料回答用户的问题。如果参考资料中没有相关信息，请明确说明。\n\n"
            "## 参考资料\n\n{context}\n\n"
            "## 用户问题\n\n{query}"
        ),
    ) -> None:
        self._embedding = embedding_provider
        self._store = vector_store
        self._chunker = chunk_strategy
        self._prompt_template = prompt_template

    async def ingest_documents(
        self,
        documents: list[Document],
        *,
        batch_size: int = 32,
        knowledge_base_id: str | None = None,
    ) -> int:
        """将文档索引到向量库。

        Args:
            documents: 待索引的文档列表。
            batch_size: Embedding 批处理大小。
            knowledge_base_id: 可选知识库 ID，写入元数据便于过滤。

        Returns:
            成功索引的分块总数。
        """
        # 分块
        all_chunks: list[Chunk] = []
        for doc in documents:
            # 不分块时，整篇作为单个 Chunk
            chunks = self._chunker.split(doc) if self._chunker else [Chunk(content=doc.content, metadata=doc.metadata)]
            for chunk in chunks:
                chunk.document_id = doc.metadata.get("document_id", str(uuid.uuid4()))
                if knowledge_base_id:
                    chunk.metadata["knowledge_base_id"] = knowledge_base_id
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        # 批量 Embedding
        total_indexed = 0
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            embeddings = await self._embedding.embed(texts)
            metadatas = [c.metadata for c in batch]
            ids = [f"{c.document_id}_{c.metadata.get('chunk_index', j)}" for j, c in enumerate(batch)]
            await self._store.add(texts, embeddings, metadatas=metadatas, ids=ids)
            total_indexed += len(batch)

        logger.info("RAG ingest 完成: %d 文档 → %d 分块", len(documents), total_indexed)
        return total_indexed

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> RAGResult:
        """检索并构造增强 Prompt。

        Args:
            query: 用户查询。
            top_k: 返回的最相关分块数量。
            filter_metadata: 元数据过滤条件。
            min_score: 最低相似度阈值。

        Returns:
            包含检索结果和增强 Prompt 的 RAGResult。
        """
        # 嵌入查询
        query_embedding = await self._embedding.embed_single(query)

        # 向量搜索
        results = await self._store.search(
            query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

        # 过滤低分结果
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        # 构造增强 Prompt
        context_parts: list[str] = []
        for i, r in enumerate(results, 1):
            source = r.metadata.get("source", "未知来源")
            context_parts.append(f"[{i}] (来源: {source}, 相似度: {r.score:.3f})\n{r.content}")

        context = "\n\n".join(context_parts) if context_parts else "未找到相关参考资料。"
        augmented_prompt = self._prompt_template.format(context=context, query=query)

        return RAGResult(
            query=query,
            results=results,
            augmented_prompt=augmented_prompt,
        )

    async def ingest_from_loader(
        self,
        loader: DocumentLoader,
        sources: list[str],
        *,
        batch_size: int = 32,
        knowledge_base_id: str | None = None,
    ) -> int:
        """从 DocumentLoader 加载并索引文档。

        Args:
            loader: 文档加载器。
            sources: 资源标识符列表（文件路径、URL 等）。
            batch_size: Embedding 批处理大小。
            knowledge_base_id: 可选知识库 ID。

        Returns:
            成功索引的分块总数。
        """
        all_docs: list[Document] = []
        for source in sources:
            docs = await loader.load(source)
            for doc in docs:
                doc.metadata.setdefault("source", source)
                doc.metadata.setdefault("document_id", str(uuid.uuid4()))
            all_docs.extend(docs)
        return await self.ingest_documents(
            all_docs,
            batch_size=batch_size,
            knowledge_base_id=knowledge_base_id,
        )
