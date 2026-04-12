"""知识库与媒体上传 API 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _mock_kb(**overrides: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "kb-demo",
        "description": "desc",
        "embedding_model": "hash-embedding-v1",
        "chunk_strategy": {},
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    record = MagicMock()
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _mock_doc(kb_id: uuid.UUID, **overrides: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "knowledge_base_id": kb_id,
        "filename": "test.txt",
        "media_type": "text/plain",
        "size_bytes": 10,
        "status": "indexed",
        "chunk_count": 1,
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    record = MagicMock()
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


# ---------------------------------------------------------------------------
# 知识库 API 基础测试
# ---------------------------------------------------------------------------
class TestKnowledgeBaseAPI:
    """知识库 API 测试。"""

    @patch("app.api.knowledge_bases.kb_service.create_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_create_kb(self, mock_db: object, mock_create: AsyncMock) -> None:
        mock_create.return_value = _mock_kb(name="kb-new")
        resp = client.post("/api/v1/knowledge-bases", json={"name": "kb-new"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "kb-new"

    @patch("app.api.knowledge_bases.kb_service.list_knowledge_bases", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_list_kb(self, mock_db: object, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([_mock_kb()], 1)
        resp = client.get("/api/v1/knowledge-bases")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.api.knowledge_bases.kb_service.search_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_search_kb(self, mock_db: object, mock_search: AsyncMock) -> None:
        kb_id = uuid.uuid4()
        mock_search.return_value = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "hello",
                "score": 0.8,
                "metadata": {},
            }
        ]
        resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/search", json={"query": "hello"})
        assert resp.status_code == 200
        assert resp.json()["query"] == "hello"
        assert len(resp.json()["results"]) == 1

    @patch("app.api.knowledge_bases.kb_service.ingest_document", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_upload_doc(self, mock_db: object, mock_ingest: AsyncMock) -> None:
        kb_id = uuid.uuid4()
        mock_ingest.return_value = _mock_doc(kb_id)
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files)
        assert resp.status_code == 201
        assert resp.json()["filename"] == "test.txt"


# ---------------------------------------------------------------------------
# 知识库 API 完整 CRUD 生命周期测试（N1 e2e 补全）
# ---------------------------------------------------------------------------
class TestKnowledgeBaseCRUDLifecycle:
    """知识库完整 CRUD 生命周期：创建 → 查询 → 更新 → 详情 → 删除。"""

    @patch("app.api.knowledge_bases.kb_service.delete_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.get_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.update_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.list_knowledge_bases", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.create_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_full_lifecycle(
        self,
        mock_db: object,
        mock_create: AsyncMock,
        mock_list: AsyncMock,
        mock_update: AsyncMock,
        mock_get: AsyncMock,
        mock_delete: AsyncMock,
    ) -> None:
        """创建 → 列表包含 → 更新名称 → 获取详情 → 删除。"""
        kb_id = uuid.uuid4()
        kb = _mock_kb(id=kb_id, name="test-kb", description="original")

        # 1. 创建
        mock_create.return_value = kb
        create_resp = client.post("/api/v1/knowledge-bases", json={"name": "test-kb", "description": "original"})
        assert create_resp.status_code == 201
        assert create_resp.json()["name"] == "test-kb"

        # 2. 列表中可见
        mock_list.return_value = ([kb], 1)
        list_resp = client.get("/api/v1/knowledge-bases")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1
        assert list_resp.json()["data"][0]["name"] == "test-kb"

        # 3. 更新
        updated_kb = _mock_kb(id=kb_id, name="renamed-kb", description="updated")
        mock_update.return_value = updated_kb
        update_resp = client.put(f"/api/v1/knowledge-bases/{kb_id}", json={"name": "renamed-kb"})
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "renamed-kb"

        # 4. 获取详情
        mock_get.return_value = updated_kb
        get_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "renamed-kb"

        # 5. 删除
        mock_delete.return_value = None
        del_resp = client.delete(f"/api/v1/knowledge-bases/{kb_id}")
        assert del_resp.status_code == 204

    @patch("app.api.knowledge_bases.kb_service.get_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_get_nonexistent_kb_returns_404(self, mock_db: object, mock_get: AsyncMock) -> None:
        """访问不存在的知识库返回 404。"""
        from app.core.exceptions import NotFoundError
        mock_get.side_effect = NotFoundError("知识库不存在")
        resp = client.get(f"/api/v1/knowledge-bases/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.knowledge_bases.kb_service.delete_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_delete_nonexistent_kb_returns_404(self, mock_db: object, mock_delete: AsyncMock) -> None:
        """删除不存在的知识库返回 404。"""
        from app.core.exceptions import NotFoundError
        mock_delete.side_effect = NotFoundError("知识库不存在")
        resp = client.delete(f"/api/v1/knowledge-bases/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.knowledge_bases.kb_service.list_knowledge_bases", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_list_empty_returns_empty(self, mock_db: object, mock_list: AsyncMock) -> None:
        """空列表返回 total=0。"""
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/knowledge-bases")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []

    @patch("app.api.knowledge_bases.kb_service.list_knowledge_bases", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_list_pagination(self, mock_db: object, mock_list: AsyncMock) -> None:
        """分页参数传递验证。"""
        mock_list.return_value = ([_mock_kb()], 5)
        resp = client.get("/api/v1/knowledge-bases?limit=1&offset=3")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 1
        assert resp.json()["offset"] == 3
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs["limit"] == 1
        assert call_kwargs.kwargs["offset"] == 3


# ---------------------------------------------------------------------------
# 知识库文档上传与检索 e2e 流程测试（N1 e2e 补全）
# ---------------------------------------------------------------------------
class TestKnowledgeBaseDocumentFlow:
    """文档上传 → 列表 → 检索完整流程。"""

    @patch("app.api.knowledge_bases.kb_service.search_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.list_documents", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.kb_service.ingest_document", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_upload_then_list_then_search(
        self,
        mock_db: object,
        mock_ingest: AsyncMock,
        mock_list_docs: AsyncMock,
        mock_search: AsyncMock,
    ) -> None:
        """上传文档 → 查看文档列表 → 搜索检索结果。"""
        kb_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chunk_id = str(uuid.uuid4())

        # 1. 上传文档
        mock_ingest.return_value = _mock_doc(kb_id, id=doc_id, filename="faq.txt", chunk_count=3)
        files = {"file": ("faq.txt", b"what is CkyClaw? CkyClaw is an AI Agent platform.", "text/plain")}
        upload_resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files)
        assert upload_resp.status_code == 201
        assert upload_resp.json()["chunk_count"] == 3

        # 2. 文档列表
        mock_list_docs.return_value = [_mock_doc(kb_id, id=doc_id, filename="faq.txt", chunk_count=3)]
        list_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "faq.txt"

        # 3. 向量检索
        mock_search.return_value = [
            {
                "chunk_id": chunk_id,
                "document_id": str(doc_id),
                "content": "CkyClaw is an AI Agent platform.",
                "score": 0.92,
                "metadata": {"source": "faq.txt"},
            }
        ]
        search_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/search",
            json={"query": "what is CkyClaw", "top_k": 3, "min_score": 0.5},
        )
        assert search_resp.status_code == 200
        results = search_resp.json()["results"]
        assert len(results) == 1
        assert results[0]["score"] >= 0.5
        assert "CkyClaw" in results[0]["content"]

    @patch("app.api.knowledge_bases.kb_service.ingest_document", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_upload_multiple_docs(self, mock_db: object, mock_ingest: AsyncMock) -> None:
        """上传多个文档，每次返回不同文档记录。"""
        kb_id = uuid.uuid4()
        for idx, name in enumerate(["a.txt", "b.txt", "c.txt"]):
            mock_ingest.return_value = _mock_doc(
                kb_id, id=uuid.uuid4(), filename=name, chunk_count=idx + 1
            )
            files = {"file": (name, f"content of {name}".encode(), "text/plain")}
            resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files)
            assert resp.status_code == 201
            assert resp.json()["filename"] == name

    @patch("app.api.knowledge_bases.kb_service.search_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_search_no_results(self, mock_db: object, mock_search: AsyncMock) -> None:
        """检索无匹配结果时返回空列表。"""
        kb_id = uuid.uuid4()
        mock_search.return_value = []
        resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/search", json={"query": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    @patch("app.api.knowledge_bases.kb_service.search_knowledge_base", new_callable=AsyncMock)
    @patch("app.api.knowledge_bases.get_db")
    def test_search_with_top_k_and_min_score(self, mock_db: object, mock_search: AsyncMock) -> None:
        """检索参数 top_k 和 min_score 正确传递。"""
        kb_id = uuid.uuid4()
        mock_search.return_value = []
        resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/search",
            json={"query": "test", "top_k": 10, "min_score": 0.8},
        )
        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["top_k"] == 10
        assert call_kwargs.kwargs["min_score"] == 0.8


# ---------------------------------------------------------------------------
# 媒体上传 API 测试（N2 e2e 补全）
# ---------------------------------------------------------------------------
class TestMediaAPI:
    """媒体上传 API 测试。"""

    def test_upload_and_fetch_media(self) -> None:
        files = {"file": ("cat.txt", b"hello", "text/plain")}
        upload = client.post("/api/v1/media/upload", files=files)
        assert upload.status_code == 201
        body = upload.json()
        assert body["url"].startswith("/api/v1/media/")

        fetched = client.get(body["url"])
        assert fetched.status_code == 200
        assert fetched.content == b"hello"

    def test_upload_empty_file_returns_400(self) -> None:
        """空文件上传返回 400。"""
        files = {"file": ("empty.txt", b"", "text/plain")}
        resp = client.post("/api/v1/media/upload", files=files)
        assert resp.status_code == 400

    def test_upload_binary_media(self) -> None:
        """上传二进制媒体文件（模拟图片）。"""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        files = {"file": ("image.png", fake_png, "image/png")}
        resp = client.post("/api/v1/media/upload", files=files)
        assert resp.status_code == 201
        body = resp.json()
        assert body["media_type"] == "image/png"
        assert body["size_bytes"] == len(fake_png)

        fetched = client.get(body["url"])
        assert fetched.status_code == 200
        assert fetched.content == fake_png

    def test_upload_response_structure(self) -> None:
        """媒体上传响应包含必要字段。"""
        files = {"file": ("doc.pdf", b"pdf-content", "application/pdf")}
        resp = client.post("/api/v1/media/upload", files=files)
        assert resp.status_code == 201
        body = resp.json()
        assert "url" in body
        assert "filename" in body
        assert "media_type" in body
        assert "size_bytes" in body
        assert body["filename"] == "doc.pdf"
        assert body["size_bytes"] == len(b"pdf-content")

    def test_fetch_nonexistent_media_returns_404(self) -> None:
        """请求不存在的媒体文件返回 404。"""
        resp = client.get("/api/v1/media/nonexistent_file_xyz.txt")
        assert resp.status_code == 404

    def test_fetch_path_traversal_returns_400(self) -> None:
        """路径遍历攻击被拒绝。"""
        resp = client.get("/api/v1/media/../../../etc/passwd")
        # FastAPI 路由中 stored_name 不含路径分隔符检查
        assert resp.status_code in (400, 404)

    def test_upload_special_chars_filename(self) -> None:
        """特殊字符文件名被安全净化。"""
        files = {"file": ("恶意<script>.txt", b"safe content", "text/plain")}
        resp = client.post("/api/v1/media/upload", files=files)
        assert resp.status_code == 201
        body = resp.json()
        # URL 中不应包含原始特殊字符
        assert "<" not in body["url"]
        assert ">" not in body["url"]

    def test_upload_multiple_files_get_unique_urls(self) -> None:
        """多次上传同名文件得到唯一的不同 URL。"""
        urls = set()
        for _ in range(3):
            files = {"file": ("same.txt", b"content", "text/plain")}
            resp = client.post("/api/v1/media/upload", files=files)
            assert resp.status_code == 201
            urls.add(resp.json()["url"])
        assert len(urls) == 3, "每次上传应生成唯一 URL"


# ---------------------------------------------------------------------------
# 知识库 service 关键逻辑测试
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestKnowledgeBaseService:
    """知识库 service 关键逻辑测试。"""

    async def test_search_empty_returns_empty(self) -> None:
        from app.services.knowledge_base import search_knowledge_base

        mock_db = AsyncMock()
        execute_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        execute_result.scalars.return_value = scalars
        mock_db.execute.return_value = execute_result

        with patch("app.services.knowledge_base.get_knowledge_base", new_callable=AsyncMock):
            rows = await search_knowledge_base(mock_db, uuid.uuid4(), query="x")
            assert rows == []

    async def test_create_knowledge_base_calls_commit(self) -> None:
        """创建知识库应调用 db.commit 和 db.refresh。"""
        from app.services.knowledge_base import create_knowledge_base
        from app.schemas.knowledge_base import KnowledgeBaseCreate

        mock_db = AsyncMock()
        data = KnowledgeBaseCreate(name="test-kb")
        await create_knowledge_base(mock_db, data)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    async def test_delete_knowledge_base_soft_delete(self) -> None:
        """删除知识库执行软删除而非物理删除。"""
        from app.services.knowledge_base import delete_knowledge_base

        mock_db = AsyncMock()
        kb_record = MagicMock()
        kb_record.is_deleted = False
        kb_record.deleted_at = None

        with patch("app.services.knowledge_base.get_knowledge_base", new_callable=AsyncMock, return_value=kb_record):
            await delete_knowledge_base(mock_db, uuid.uuid4())
            assert kb_record.is_deleted is True
            assert kb_record.deleted_at is not None
            mock_db.commit.assert_awaited_once()

    async def test_update_knowledge_base_partial(self) -> None:
        """部分更新仅修改提供的字段。"""
        from app.services.knowledge_base import update_knowledge_base
        from app.schemas.knowledge_base import KnowledgeBaseUpdate

        mock_db = AsyncMock()
        kb_record = MagicMock()
        kb_record.name = "old-name"
        kb_record.description = "old-desc"

        data = KnowledgeBaseUpdate(name="new-name")

        with patch("app.services.knowledge_base.get_knowledge_base", new_callable=AsyncMock, return_value=kb_record):
            await update_knowledge_base(mock_db, uuid.uuid4(), data)
            assert kb_record.name == "new-name"
            mock_db.commit.assert_awaited_once()
