"""Artifact Store 测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from ckyclaw_framework.artifacts import Artifact, InMemoryArtifactStore, LocalArtifactStore
from ckyclaw_framework.artifacts.store import _estimate_token_count, _make_summary

if TYPE_CHECKING:
    from pathlib import Path

# ───────── Artifact 数据类测试 ─────────

class TestArtifact:
    """Artifact 数据类单元测试。"""

    def test_to_dict_and_from_dict(self) -> None:
        """序列化 → 反序列化完整往返。"""
        artifact = Artifact(
            artifact_id="abc123",
            run_id="run-1",
            content="Hello world!",
            summary="Hello world!",
            token_count=4,
            metadata={"tool_name": "search"},
        )
        data = artifact.to_dict()
        restored = Artifact.from_dict(data)
        assert restored.artifact_id == "abc123"
        assert restored.run_id == "run-1"
        assert restored.content == "Hello world!"
        assert restored.summary == "Hello world!"
        assert restored.token_count == 4
        assert restored.metadata == {"tool_name": "search"}

    def test_from_dict_defaults(self) -> None:
        """缺失字段使用默认值。"""
        restored = Artifact.from_dict({})
        assert restored.run_id == ""
        assert restored.content == ""
        assert restored.token_count == 0
        assert isinstance(restored.created_at, datetime)

    def test_from_dict_datetime_string(self) -> None:
        """ISO 格式时间字符串正确解析。"""
        restored = Artifact.from_dict({"created_at": "2026-04-11T10:00:00+00:00"})
        assert restored.created_at.year == 2026
        assert restored.created_at.month == 4

    def test_default_artifact_id_is_unique(self) -> None:
        """默认 artifact_id 是唯一的。"""
        a1 = Artifact()
        a2 = Artifact()
        assert a1.artifact_id != a2.artifact_id


# ───────── 辅助函数测试 ─────────

class TestHelpers:
    """辅助函数测试。"""

    def test_make_summary_short_content(self) -> None:
        """短内容不截断。"""
        assert _make_summary("hello") == "hello"

    def test_make_summary_long_content(self) -> None:
        """长内容被截断到 max_chars + 省略标记。"""
        long_text = "x" * 500
        summary = _make_summary(long_text, max_chars=100)
        assert len(summary) == 100 + len("... [truncated]")
        assert summary.endswith("... [truncated]")

    def test_make_summary_exact_boundary(self) -> None:
        """刚好等于 max_chars 不截断。"""
        text = "x" * 200
        assert _make_summary(text, max_chars=200) == text

    def test_estimate_token_count(self) -> None:
        """Token 估算逻辑。"""
        assert _estimate_token_count("abc") == 1  # 3/3=1
        assert _estimate_token_count("a" * 300) == 100  # 300/3=100
        assert _estimate_token_count("") == 1  # max(0, 1)


# ───────── InMemoryArtifactStore 测试 ─────────

class TestInMemoryArtifactStore:
    """内存 Artifact Store 测试。"""

    @pytest.fixture()
    def store(self) -> InMemoryArtifactStore:
        return InMemoryArtifactStore()

    @pytest.mark.asyncio()
    async def test_save_and_load(self, store: InMemoryArtifactStore) -> None:
        """保存后能正确读取。"""
        artifact = await store.save("run-1", "some content", {"tool": "test"})
        assert artifact.run_id == "run-1"
        assert artifact.content == "some content"
        assert artifact.metadata == {"tool": "test"}

        loaded = await store.load(artifact.artifact_id)
        assert loaded is not None
        assert loaded.content == "some content"

    @pytest.mark.asyncio()
    async def test_save_generates_summary(self, store: InMemoryArtifactStore) -> None:
        """保存时自动生成摘要。"""
        content = "x" * 1000
        artifact = await store.save("run-1", content)
        assert len(artifact.summary) < len(content)
        assert artifact.summary.endswith("... [truncated]")

    @pytest.mark.asyncio()
    async def test_load_nonexistent(self, store: InMemoryArtifactStore) -> None:
        """不存在的 artifact 返回 None。"""
        result = await store.load("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio()
    async def test_list_by_run(self, store: InMemoryArtifactStore) -> None:
        """按 run_id 查询。"""
        await store.save("run-1", "a")
        await store.save("run-1", "b")
        await store.save("run-2", "c")

        run1_artifacts = await store.list_by_run("run-1")
        assert len(run1_artifacts) == 2

        run2_artifacts = await store.list_by_run("run-2")
        assert len(run2_artifacts) == 1

    @pytest.mark.asyncio()
    async def test_cleanup(self, store: InMemoryArtifactStore) -> None:
        """过期 artifact 被删除。"""
        a = await store.save("run-1", "old content")
        # 手动设置为旧时间
        a.created_at = datetime(2020, 1, 1, tzinfo=UTC)

        await store.save("run-1", "new content")

        deleted = await store.cleanup(datetime(2025, 1, 1, tzinfo=UTC))
        assert deleted == 1
        assert await store.load(a.artifact_id) is None

    @pytest.mark.asyncio()
    async def test_save_estimates_tokens(self, store: InMemoryArtifactStore) -> None:
        """保存时自动估算 token 数。"""
        artifact = await store.save("run-1", "a" * 300)
        assert artifact.token_count == 100


# ───────── LocalArtifactStore 测试 ─────────

class TestLocalArtifactStore:
    """本地文件系统 Artifact Store 测试。"""

    @pytest.fixture()
    def store(self, tmp_path: Path) -> LocalArtifactStore:
        return LocalArtifactStore(tmp_path / "artifacts")

    @pytest.mark.asyncio()
    async def test_save_creates_file(self, store: LocalArtifactStore) -> None:
        """保存时创建 JSON 文件。"""
        artifact = await store.save("run-1", "file content")
        path = store._artifact_path("run-1", artifact.artifact_id)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["content"] == "file content"

    @pytest.mark.asyncio()
    async def test_save_and_load(self, store: LocalArtifactStore) -> None:
        """保存后能正确读取。"""
        artifact = await store.save("run-1", "hello world")
        loaded = await store.load(artifact.artifact_id)
        assert loaded is not None
        assert loaded.content == "hello world"
        assert loaded.artifact_id == artifact.artifact_id

    @pytest.mark.asyncio()
    async def test_load_nonexistent(self, store: LocalArtifactStore) -> None:
        """不存在的 artifact 返回 None。"""
        result = await store.load("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio()
    async def test_list_by_run(self, store: LocalArtifactStore) -> None:
        """按 run_id 查询。"""
        await store.save("run-1", "a")
        await store.save("run-1", "b")
        await store.save("run-2", "c")

        run1 = await store.list_by_run("run-1")
        assert len(run1) == 2
        run2 = await store.list_by_run("run-2")
        assert len(run2) == 1

    @pytest.mark.asyncio()
    async def test_list_by_run_empty(self, store: LocalArtifactStore) -> None:
        """不存在的 run_id 返回空列表。"""
        result = await store.list_by_run("nonexistent")
        assert result == []

    @pytest.mark.asyncio()
    async def test_cleanup(self, store: LocalArtifactStore) -> None:
        """过期 artifact 文件被删除。"""
        artifact = await store.save("run-old", "old data")
        # 修改文件中的 created_at 为过去时间
        path = store._artifact_path("run-old", artifact.artifact_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["created_at"] = "2020-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")

        deleted = await store.cleanup(datetime(2025, 1, 1, tzinfo=UTC))
        assert deleted == 1
        assert not path.exists()

    @pytest.mark.asyncio()
    async def test_cleanup_removes_empty_dir(self, store: LocalArtifactStore) -> None:
        """清理后空目录也被删除。"""
        artifact = await store.save("run-empty", "temp")
        path = store._artifact_path("run-empty", artifact.artifact_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["created_at"] = "2020-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")

        await store.cleanup(datetime(2025, 1, 1, tzinfo=UTC))
        run_dir = path.parent
        assert not run_dir.exists()

    @pytest.mark.asyncio()
    async def test_path_traversal_protection(self, store: LocalArtifactStore) -> None:
        """路径穿越攻击被防御。"""
        artifact = await store.save("../../../etc", "malicious")
        # 实际路径不应穿越到 base_dir 之外
        path = store._artifact_path("../../../etc", artifact.artifact_id)
        assert store._base_dir in path.parents or path.parent == store._base_dir / "______etc"
