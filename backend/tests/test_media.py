"""Media 文件上传下载 API 测试 — 上传 / 下载 / 路径遍历安全 / 文件名清洗。"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# 使用临时目录，避免污染真实 uploads
TEST_UPLOAD_DIR = Path("uploads/media_test_" + uuid.uuid4().hex[:8])


@pytest.fixture(autouse=True)
def _use_temp_upload_dir():
    """将 media 上传目录重定向到临时目录。"""
    TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with patch("app.api.media._UPLOAD_DIR", TEST_UPLOAD_DIR):
        yield
    shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)


class TestMediaUpload:
    """POST /api/v1/media/upload 文件上传。"""

    def test_upload_success(self) -> None:
        """成功上传文件，返回 URL 和元信息。"""
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "url" in body
        assert body["filename"] == "test.txt"
        assert body["media_type"] == "text/plain"
        assert body["size_bytes"] == 11

    def test_upload_image(self) -> None:
        """上传图片文件。"""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("photo.png", fake_png, "image/png")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["filename"] == "photo.png"
        assert body["size_bytes"] == len(fake_png)

    def test_upload_generates_unique_url(self) -> None:
        """每次上传生成唯一存储路径。"""
        resp1 = client.post(
            "/api/v1/media/upload",
            files={"file": ("dup.txt", b"a", "text/plain")},
        )
        resp2 = client.post(
            "/api/v1/media/upload",
            files={"file": ("dup.txt", b"b", "text/plain")},
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["url"] != resp2.json()["url"]


class TestMediaDownload:
    """GET /api/v1/media/{stored_name} 文件下载。"""

    def test_download_uploaded_file(self) -> None:
        """上传后可以成功下载。"""
        content = b"download test content"
        upload_resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("dl.txt", content, "text/plain")},
        )
        assert upload_resp.status_code == 201
        url = upload_resp.json()["url"]
        dl_resp = client.get(url)
        assert dl_resp.status_code == 200
        assert dl_resp.content == content

    def test_download_not_found(self) -> None:
        """下载不存在的文件返回 404。"""
        resp = client.get("/api/v1/media/nonexistent-file.txt")
        assert resp.status_code == 404


class TestMediaSecurity:
    """路径遍历与文件名安全。"""

    def test_path_traversal_blocked(self) -> None:
        """包含 / 或 \\ 的存储名应被拒绝。"""
        resp = client.get("/api/v1/media/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404, 422)

    def test_path_traversal_backslash(self) -> None:
        """反斜杠路径遍历。"""
        resp = client.get("/api/v1/media/..\\..\\etc\\passwd")
        assert resp.status_code in (400, 404, 422)

    def test_sanitize_special_chars_in_filename(self) -> None:
        """上传文件名含特殊字符时被清洗。"""
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("../../evil.sh", b"bad", "application/octet-stream")},
        )
        assert resp.status_code == 201
        body = resp.json()
        # 存储的文件名不应包含路径分隔符
        stored_name = body["url"].split("/")[-1]
        assert "/" not in stored_name
        assert "\\" not in stored_name
