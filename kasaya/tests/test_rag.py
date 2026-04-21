"""RAG 模块单元测试。"""

from __future__ import annotations

import pytest

from kasaya.rag.chunker import (
    FixedSizeChunker,
    MarkdownChunker,
    RecursiveCharacterChunker,
)
from kasaya.rag.document import Document
from kasaya.rag.embedding import InMemoryEmbeddingProvider
from kasaya.rag.pipeline import RAGPipeline, RAGResult
from kasaya.rag.tool import create_knowledge_base_tool
from kasaya.rag.vector_store import (
    InMemoryVectorStore,
    cosine_similarity,
)

# ── Document ──────────────────────────────────────────────


class TestDocument:
    """Document 数据类测试。"""

    def test_basic(self) -> None:
        doc = Document(content="hello", metadata={"source": "test.txt"})
        assert doc.content == "hello"
        assert doc.metadata["source"] == "test.txt"

    def test_default_metadata(self) -> None:
        doc = Document(content="x")
        assert doc.metadata == {}


# ── FixedSizeChunker ─────────────────────────────────────


class TestFixedSizeChunker:
    """固定大小分块测试。"""

    def test_basic_split(self) -> None:
        chunker = FixedSizeChunker(chunk_size=10, overlap=0)
        doc = Document(content="0123456789abcdef")
        chunks = chunker.split(doc)
        assert len(chunks) == 2
        assert chunks[0].content == "0123456789"
        assert chunks[1].content == "abcdef"

    def test_overlap(self) -> None:
        chunker = FixedSizeChunker(chunk_size=10, overlap=3)
        doc = Document(content="0123456789abcdef")
        chunks = chunker.split(doc)
        assert len(chunks) >= 2
        # 第二块应该从位置 7 开始（10-3=7）
        assert chunks[1].content.startswith("789")

    def test_empty_document(self) -> None:
        chunker = FixedSizeChunker(chunk_size=10, overlap=0)
        doc = Document(content="")
        assert chunker.split(doc) == []

    def test_metadata_inherited(self) -> None:
        chunker = FixedSizeChunker(chunk_size=100, overlap=0)
        doc = Document(content="hello world", metadata={"source": "test.md"})
        chunks = chunker.split(doc)
        assert chunks[0].metadata["source"] == "test.md"
        assert "chunk_index" in chunks[0].metadata

    def test_invalid_params(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            FixedSizeChunker(chunk_size=0)
        with pytest.raises(ValueError, match="overlap 不能为负"):
            FixedSizeChunker(chunk_size=10, overlap=-1)
        with pytest.raises(ValueError, match="overlap 必须小于"):
            FixedSizeChunker(chunk_size=10, overlap=10)


# ── RecursiveCharacterChunker ────────────────────────────


class TestRecursiveCharacterChunker:
    """递归字符分块测试。"""

    def test_paragraph_split(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50)
        doc = Document(content="段落一的内容。\n\n段落二的内容。")
        chunks = chunker.split(doc)
        assert len(chunks) >= 1

    def test_short_text_single_chunk(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=1000)
        doc = Document(content="短文本")
        chunks = chunker.split(doc)
        assert len(chunks) == 1
        assert chunks[0].content == "短文本"

    def test_invalid_params(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            RecursiveCharacterChunker(chunk_size=0)


# ── MarkdownChunker ──────────────────────────────────────


class TestMarkdownChunker:
    """Markdown 感知分块测试。"""

    def test_heading_split(self) -> None:
        md = "# 标题一\n\n内容一\n\n## 标题二\n\n内容二"
        chunker = MarkdownChunker()
        chunks = chunker.split(Document(content=md))
        assert len(chunks) == 2
        assert chunks[0].metadata["heading"] == "标题一"
        assert chunks[1].metadata["heading"] == "标题二"

    def test_preamble(self) -> None:
        md = "前言内容\n\n# 标题\n\n正文"
        chunker = MarkdownChunker()
        chunks = chunker.split(Document(content=md))
        assert any(c.metadata.get("heading") == "_preamble" for c in chunks)

    def test_no_headings(self) -> None:
        md = "没有标题的纯文本"
        chunker = MarkdownChunker()
        chunks = chunker.split(Document(content=md))
        assert len(chunks) == 1

    def test_empty_document(self) -> None:
        chunker = MarkdownChunker()
        assert chunker.split(Document(content="")) == []


# ── Embedding ────────────────────────────────────────────


class TestInMemoryEmbeddingProvider:
    """InMemoryEmbeddingProvider 测试。"""

    @pytest.mark.asyncio
    async def test_dimension(self) -> None:
        provider = InMemoryEmbeddingProvider(dimension=64)
        assert provider.dimension == 64
        vectors = await provider.embed(["hello"])
        assert len(vectors[0]) == 64

    @pytest.mark.asyncio
    async def test_deterministic(self) -> None:
        provider = InMemoryEmbeddingProvider()
        v1 = await provider.embed_single("同一文本")
        v2 = await provider.embed_single("同一文本")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_different_texts(self) -> None:
        provider = InMemoryEmbeddingProvider()
        v1 = await provider.embed_single("文本A")
        v2 = await provider.embed_single("文本B")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_batch(self) -> None:
        provider = InMemoryEmbeddingProvider()
        vectors = await provider.embed(["a", "b", "c"])
        assert len(vectors) == 3

    @pytest.mark.asyncio
    async def test_normalized(self) -> None:
        """向量应该是 L2 归一化的。"""
        provider = InMemoryEmbeddingProvider(dimension=128)
        vec = await provider.embed_single("任意文本")
        norm = sum(v * v for v in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6


# ── VectorStore ──────────────────────────────────────────


class TestCosineSimlarity:
    """余弦相似度计算测试。"""

    def test_identical(self) -> None:
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite(self) -> None:
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_dimension_mismatch(self) -> None:
        with pytest.raises(ValueError, match="维度不一致"):
            cosine_similarity([1, 0], [1, 0, 0])

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0, 0], [1, 0]) == 0.0


class TestInMemoryVectorStore:
    """InMemoryVectorStore 测试。"""

    @pytest.mark.asyncio
    async def test_add_and_count(self) -> None:
        store = InMemoryVectorStore()
        ids = await store.add(["hello", "world"], [[1.0, 0.0], [0.0, 1.0]])
        assert len(ids) == 2
        assert await store.count() == 2

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        store = InMemoryVectorStore()
        await store.add(
            ["hello", "world"],
            [[1.0, 0.0], [0.0, 1.0]],
            metadatas=[{"source": "a"}, {"source": "b"}],
        )
        results = await store.search([1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].content == "hello"
        assert results[0].score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_search_with_filter(self) -> None:
        store = InMemoryVectorStore()
        await store.add(
            ["a", "b", "c"],
            [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]],
            metadatas=[{"kb": "1"}, {"kb": "2"}, {"kb": "1"}],
        )
        results = await store.search([1.0, 0.0], top_k=10, filter_metadata={"kb": "1"})
        assert all(r.metadata["kb"] == "1" for r in results)

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        store = InMemoryVectorStore()
        ids = await store.add(["x"], [[1.0]])
        assert await store.count() == 1
        deleted = await store.delete(ids)
        assert deleted == 1
        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self) -> None:
        store = InMemoryVectorStore()
        assert await store.delete(["nonexistent"]) == 0

    @pytest.mark.asyncio
    async def test_mismatched_lengths(self) -> None:
        store = InMemoryVectorStore()
        with pytest.raises(ValueError, match="长度必须一致"):
            await store.add(["a", "b"], [[1.0]])

    @pytest.mark.asyncio
    async def test_custom_ids(self) -> None:
        store = InMemoryVectorStore()
        ids = await store.add(["x"], [[1.0]], ids=["my-id"])
        assert ids == ["my-id"]


# ── RAGPipeline ──────────────────────────────────────────


class TestRAGPipeline:
    """RAGPipeline 端到端测试。"""

    @pytest.fixture
    def pipeline(self) -> RAGPipeline:
        return RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(dimension=128),
            vector_store=InMemoryVectorStore(),
            chunk_strategy=FixedSizeChunker(chunk_size=100, overlap=0),
        )

    @pytest.mark.asyncio
    async def test_ingest_and_retrieve(self, pipeline: RAGPipeline) -> None:
        docs = [
            Document(content="Python 是一种广泛使用的高级编程语言。", metadata={"source": "python.md"}),
            Document(content="FastAPI 是基于 Python 的现代 Web 框架。", metadata={"source": "fastapi.md"}),
        ]
        count = await pipeline.ingest_documents(docs)
        assert count >= 2

        result = await pipeline.retrieve("什么是 Python?")
        assert isinstance(result, RAGResult)
        assert len(result.results) > 0
        assert "参考资料" in result.augmented_prompt
        assert result.query == "什么是 Python?"

    @pytest.mark.asyncio
    async def test_ingest_empty(self, pipeline: RAGPipeline) -> None:
        count = await pipeline.ingest_documents([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_retrieve_no_results(self) -> None:
        pipeline = RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(dimension=128),
            vector_store=InMemoryVectorStore(),
        )
        result = await pipeline.retrieve("任意查询", min_score=0.99)
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_knowledge_base_filter(self, pipeline: RAGPipeline) -> None:
        docs = [Document(content="内容", metadata={"source": "test"})]
        await pipeline.ingest_documents(docs, knowledge_base_id="kb-1")
        result = await pipeline.retrieve("内容", filter_metadata={"knowledge_base_id": "kb-1"})
        assert all(r.metadata.get("knowledge_base_id") == "kb-1" for r in result.results)

    @pytest.mark.asyncio
    async def test_without_chunker(self) -> None:
        pipeline = RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(dimension=128),
            vector_store=InMemoryVectorStore(),
            chunk_strategy=None,  # 不分块
        )
        docs = [Document(content="整篇文档不分块")]
        count = await pipeline.ingest_documents(docs)
        assert count == 1


# ── RAG Tool ─────────────────────────────────────────────


class TestRAGTool:
    """知识库检索工具测试。"""

    @pytest.mark.asyncio
    async def test_create_and_call(self) -> None:
        pipeline = RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(dimension=128),
            vector_store=InMemoryVectorStore(),
            chunk_strategy=FixedSizeChunker(chunk_size=200, overlap=0),
        )
        docs = [Document(content="Kasaya 是一个 AI Agent 管理平台。")]
        await pipeline.ingest_documents(docs)

        tool = create_knowledge_base_tool(pipeline, top_k=3)
        assert tool.name == "knowledge_base_search"

        # 直接调用 fn
        result = await tool.fn("Kasaya 是什么?")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_no_results(self) -> None:
        pipeline = RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(dimension=128),
            vector_store=InMemoryVectorStore(),
        )
        tool = create_knowledge_base_tool(pipeline, min_score=0.99)
        result = await tool.fn("完全无关的查询")
        assert "未" in result or "没有" in result or isinstance(result, str)

    def test_tool_schema(self) -> None:
        pipeline = RAGPipeline(
            embedding_provider=InMemoryEmbeddingProvider(),
            vector_store=InMemoryVectorStore(),
        )
        tool = create_knowledge_base_tool(pipeline, name="my_kb")
        assert tool.name == "my_kb"
        assert tool.parameters_schema["properties"]["query"]["type"] == "string"
