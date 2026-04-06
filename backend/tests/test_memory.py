"""Memory 记忆系统 CRUD + 搜索 + 衰减 API 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ═══════════════════════════════════════════════════════════════════
# Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


def _make_memory_entry(**overrides: Any) -> MagicMock:
    """构造模拟 MemoryEntryRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "user_id": "user-001",
        "type": "structured_fact",
        "content": "项目使用 PostgreSQL 16",
        "confidence": 0.95,
        "agent_name": "coding-agent",
        "source_session_id": None,
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ═══════════════════════════════════════════════════════════════════
# Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestMemorySchemas:
    """Memory Schema 验证。"""

    def test_memory_response_model_validate(self) -> None:
        from app.schemas.memory import MemoryResponse
        mock = _make_memory_entry()
        resp = MemoryResponse.model_validate(mock)
        assert resp.user_id == "user-001"
        assert resp.type == "structured_fact"
        assert resp.confidence == 0.95

    def test_memory_create_validation(self) -> None:
        from app.schemas.memory import MemoryCreate
        data = MemoryCreate(
            type="user_profile",
            content="偏好 Python",
            user_id="u1",
            confidence=0.9,
        )
        assert data.type == "user_profile"
        assert data.content == "偏好 Python"

    def test_memory_create_invalid_type(self) -> None:
        from app.schemas.memory import MemoryCreate
        with pytest.raises(Exception):
            MemoryCreate(type="invalid", content="x", user_id="u1")

    def test_memory_create_empty_content(self) -> None:
        from app.schemas.memory import MemoryCreate
        with pytest.raises(Exception):
            MemoryCreate(type="structured_fact", content="", user_id="u1")

    def test_memory_create_confidence_bounds(self) -> None:
        from app.schemas.memory import MemoryCreate
        with pytest.raises(Exception):
            MemoryCreate(type="structured_fact", content="x", user_id="u1", confidence=1.5)
        with pytest.raises(Exception):
            MemoryCreate(type="structured_fact", content="x", user_id="u1", confidence=-0.1)

    def test_memory_update_partial(self) -> None:
        from app.schemas.memory import MemoryUpdate
        data = MemoryUpdate(content="新内容")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"content": "新内容"}

    def test_memory_search_request(self) -> None:
        from app.schemas.memory import MemorySearchRequest
        req = MemorySearchRequest(user_id="u1", query="Python")
        assert req.user_id == "u1"
        assert req.limit == 10  # default

    def test_memory_decay_request(self) -> None:
        from app.schemas.memory import MemoryDecayRequest
        req = MemoryDecayRequest(
            before=datetime(2024, 1, 1, tzinfo=timezone.utc),
            rate=0.05,
        )
        assert req.rate == 0.05


# ═══════════════════════════════════════════════════════════════════
# API 路由测试
# ═══════════════════════════════════════════════════════════════════

client = TestClient(app)


class TestMemoryAPI:
    """Memory API 端点测试。"""

    @patch("app.api.memories.memory_service.create_memory", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_create_memory(self, mock_db: Any, mock_create: AsyncMock) -> None:
        mock_create.return_value = _make_memory_entry()
        resp = client.post("/api/v1/memories", json={
            "type": "structured_fact",
            "content": "项目使用 PostgreSQL 16",
            "user_id": "user-001",
            "confidence": 0.95,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "user-001"
        assert data["type"] == "structured_fact"

    @patch("app.api.memories.memory_service.list_memories", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_list_memories(self, mock_db: Any, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([_make_memory_entry()], 1)
        resp = client.get("/api/v1/memories?user_id=user-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["data"]) == 1

    @patch("app.api.memories.memory_service.get_memory", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_get_memory(self, mock_db: Any, mock_get: AsyncMock) -> None:
        entry_id = uuid.uuid4()
        mock_get.return_value = _make_memory_entry(id=entry_id)
        resp = client.get(f"/api/v1/memories/{entry_id}")
        assert resp.status_code == 200

    @patch("app.api.memories.memory_service.update_memory", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_update_memory(self, mock_db: Any, mock_update: AsyncMock) -> None:
        entry_id = uuid.uuid4()
        mock_update.return_value = _make_memory_entry(id=entry_id, content="更新后的内容")
        resp = client.put(f"/api/v1/memories/{entry_id}", json={
            "content": "更新后的内容",
        })
        assert resp.status_code == 200
        assert resp.json()["content"] == "更新后的内容"

    @patch("app.api.memories.memory_service.delete_memory", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_delete_memory(self, mock_db: Any, mock_delete: AsyncMock) -> None:
        entry_id = uuid.uuid4()
        mock_delete.return_value = None
        resp = client.delete(f"/api/v1/memories/{entry_id}")
        assert resp.status_code == 204

    @patch("app.api.memories.memory_service.delete_user_memories", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_delete_user_memories(self, mock_db: Any, mock_del: AsyncMock) -> None:
        mock_del.return_value = 5
        resp = client.delete("/api/v1/memories/user/user-001")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 5

    @patch("app.api.memories.memory_service.search_memories", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_search_memories(self, mock_db: Any, mock_search: AsyncMock) -> None:
        mock_search.return_value = [_make_memory_entry()]
        resp = client.post("/api/v1/memories/search", json={
            "user_id": "user-001",
            "query": "PostgreSQL",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @patch("app.api.memories.memory_service.decay_memories", new_callable=AsyncMock)
    @patch("app.api.memories.get_db")
    def test_decay_memories(self, mock_db: Any, mock_decay: AsyncMock) -> None:
        mock_decay.return_value = 10
        resp = client.post("/api/v1/memories/decay", json={
            "before": "2024-01-01T00:00:00Z",
            "rate": 0.05,
        })
        assert resp.status_code == 200
        assert resp.json()["affected"] == 10


# ═══════════════════════════════════════════════════════════════════
# Service 层逻辑测试（mock DB）
# ═══════════════════════════════════════════════════════════════════


class TestMemoryService:
    """Memory Service 逻辑验证。"""

    @pytest.mark.asyncio
    @patch("app.services.memory.AsyncSession", new_callable=MagicMock)
    async def test_create_memory_service(self, mock_session_cls: Any) -> None:
        from app.schemas.memory import MemoryCreate
        from app.services.memory import create_memory

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        data = MemoryCreate(
            type="structured_fact",
            content="测试内容",
            user_id="u1",
        )
        result = await create_memory(mock_db, data)
        assert mock_db.add.called
        assert mock_db.commit.called


# ═══════════════════════════════════════════════════════════════════
# M-Opt: Memory 优化 — 衰减模式 + Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestMemoryDecayModeSchema:
    """DecayMode Schema 验证。"""

    def test_default_mode_is_linear(self) -> None:
        """默认衰减模式为 LINEAR。"""
        from app.schemas.memory import MemoryDecayRequest

        req = MemoryDecayRequest(
            before=datetime.now(timezone.utc), rate=0.05
        )
        assert req.mode.value == "linear"

    def test_exponential_mode(self) -> None:
        """exponential 模式有效。"""
        from app.schemas.memory import MemoryDecayModeEnum, MemoryDecayRequest

        req = MemoryDecayRequest(
            before=datetime.now(timezone.utc),
            rate=0.1,
            mode=MemoryDecayModeEnum.EXPONENTIAL,
        )
        assert req.mode == MemoryDecayModeEnum.EXPONENTIAL

    def test_invalid_mode_rejected(self) -> None:
        """无效模式被拒绝。"""
        from app.schemas.memory import MemoryDecayRequest

        with pytest.raises(ValueError):
            MemoryDecayRequest(
                before=datetime.now(timezone.utc), rate=0.05, mode="invalid"
            )


class TestMemoryDecayService:
    """decay_memories 服务层指数衰减测试。"""

    @pytest.mark.asyncio
    async def test_linear_decay_uses_bulk_update(self) -> None:
        """线性衰减使用批量 UPDATE。"""
        from app.schemas.memory import MemoryDecayModeEnum, MemoryDecayRequest
        from app.services.memory import decay_memories

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute = AsyncMock(return_value=mock_result)

        data = MemoryDecayRequest(
            before=datetime.now(timezone.utc), rate=0.05
        )
        count = await decay_memories(mock_db, data)
        assert count == 5
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_exponential_decay_processes_records(self) -> None:
        """指数衰减逐条处理记录。"""
        from app.schemas.memory import MemoryDecayModeEnum, MemoryDecayRequest
        from app.services.memory import decay_memories

        # 创建 mock 记录
        record1 = MagicMock()
        record1.updated_at = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=10)
        record1.confidence = 1.0

        record2 = MagicMock()
        record2.updated_at = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)
        record2.confidence = 0.8

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [record1, record2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        data = MemoryDecayRequest(
            before=datetime.now(timezone.utc),
            rate=0.1,
            mode=MemoryDecayModeEnum.EXPONENTIAL,
        )
        count = await decay_memories(mock_db, data)
        assert count == 2
        # record1: 10 days, λ=0.1 → 1.0 × e^(-1) ≈ 0.368
        assert 0.3 < record1.confidence < 0.5
        # record2: 30 days, λ=0.1 → 0.8 × e^(-3) ≈ 0.04
        assert 0.0 < record2.confidence < 0.1
        mock_db.commit.assert_awaited()


class TestDecayAPIWithMode:
    """衰减 API 端点 + 模式参数测试。"""

    @patch("app.api.memories.require_permission")
    @patch("app.api.memories.get_db")
    @patch("app.api.memories.memory_service.decay_memories", new_callable=AsyncMock)
    def test_decay_with_exponential_mode(
        self, mock_decay: AsyncMock, mock_db: Any, mock_perm: Any
    ) -> None:
        """POST /api/v1/memories/decay 支持 exponential 模式。"""
        mock_decay.return_value = 3
        mock_db.return_value.__aenter__ = AsyncMock()
        mock_db.return_value.__aexit__ = AsyncMock()

        resp = client.post(
            "/api/v1/memories/decay",
            json={
                "before": "2024-01-01T00:00:00Z",
                "rate": 0.1,
                "mode": "exponential",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 3
