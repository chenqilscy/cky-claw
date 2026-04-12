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
