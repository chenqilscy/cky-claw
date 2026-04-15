"""A2A 协议 API 和 Service 测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_agent_card(**overrides: object) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "name": "test-card",
        "description": "Test Agent Card",
        "url": "https://example.com/a2a",
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "skills": [{"id": "s1", "name": "Skill1"}],
        "authentication": {},
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    record = MagicMock()
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _mock_task(**overrides: object) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_card_id": uuid.uuid4(),
        "status": "submitted",
        "input_messages": [{"role": "user", "parts": [{"type": "text/plain", "text": "hello"}]}],
        "artifacts": [],
        "history": [{"status": "submitted", "timestamp": now.isoformat(), "message": "任务创建"}],
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
# Agent Card API 测试
# ---------------------------------------------------------------------------
class TestA2AAgentCardAPI:
    """A2A Agent Card CRUD API 测试。"""

    @patch("app.api.a2a.a2a_service.create_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_create_agent_card(self, mock_db: object, mock_create: AsyncMock) -> None:
        agent_id = uuid.uuid4()
        mock_create.return_value = _mock_agent_card(name="new-card", agent_id=agent_id)
        resp = client.post("/api/v1/a2a/agent-cards", json={
            "agent_id": str(agent_id),
            "name": "new-card",
            "url": "https://example.com/a2a",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "new-card"

    @patch("app.api.a2a.a2a_service.list_agent_cards", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_list_agent_cards(self, mock_db: object, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([_mock_agent_card()], 1)
        resp = client.get("/api/v1/a2a/agent-cards")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.api.a2a.a2a_service.get_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_get_agent_card(self, mock_db: object, mock_get: AsyncMock) -> None:
        card_id = uuid.uuid4()
        mock_get.return_value = _mock_agent_card(id=card_id, name="found-card")
        resp = client.get(f"/api/v1/a2a/agent-cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "found-card"

    @patch("app.api.a2a.a2a_service.update_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_update_agent_card(self, mock_db: object, mock_update: AsyncMock) -> None:
        card_id = uuid.uuid4()
        mock_update.return_value = _mock_agent_card(id=card_id, name="updated-card")
        resp = client.put(f"/api/v1/a2a/agent-cards/{card_id}", json={"name": "updated-card"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-card"

    @patch("app.api.a2a.a2a_service.delete_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_delete_agent_card(self, mock_db: object, mock_delete: AsyncMock) -> None:
        card_id = uuid.uuid4()
        mock_delete.return_value = None
        resp = client.delete(f"/api/v1/a2a/agent-cards/{card_id}")
        assert resp.status_code == 204

    @patch("app.api.a2a.a2a_service.get_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_get_nonexistent_card_returns_404(self, mock_db: object, mock_get: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        mock_get.side_effect = NotFoundError("不存在")
        resp = client.get(f"/api/v1/a2a/agent-cards/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.a2a.a2a_service.list_agent_cards", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_list_empty(self, mock_db: object, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/a2a/agent-cards")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# Agent Card CRUD 生命周期测试
# ---------------------------------------------------------------------------
class TestA2AAgentCardLifecycle:
    """Agent Card 完整 CRUD 生命周期。"""

    @patch("app.api.a2a.a2a_service.delete_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.get_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.update_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.list_agent_cards", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.create_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_full_lifecycle(
        self,
        mock_db: object,
        mock_create: AsyncMock,
        mock_list: AsyncMock,
        mock_update: AsyncMock,
        mock_get: AsyncMock,
        mock_delete: AsyncMock,
    ) -> None:
        """创建 → 列表 → 更新 → 详情 → 删除。"""
        card_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        card = _mock_agent_card(id=card_id, agent_id=agent_id, name="lifecycle-card")

        # 创建
        mock_create.return_value = card
        resp = client.post("/api/v1/a2a/agent-cards", json={
            "agent_id": str(agent_id), "name": "lifecycle-card",
        })
        assert resp.status_code == 201

        # 列表
        mock_list.return_value = ([card], 1)
        resp = client.get("/api/v1/a2a/agent-cards")
        assert resp.json()["total"] == 1

        # 更新
        updated = _mock_agent_card(id=card_id, name="renamed")
        mock_update.return_value = updated
        resp = client.put(f"/api/v1/a2a/agent-cards/{card_id}", json={"name": "renamed"})
        assert resp.json()["name"] == "renamed"

        # 详情
        mock_get.return_value = updated
        resp = client.get(f"/api/v1/a2a/agent-cards/{card_id}")
        assert resp.json()["name"] == "renamed"

        # 删除
        mock_delete.return_value = None
        resp = client.delete(f"/api/v1/a2a/agent-cards/{card_id}")
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# 服务发现 API 测试
# ---------------------------------------------------------------------------
class TestA2ADiscoveryAPI:
    """A2A 服务发现 API 测试。"""

    @patch("app.api.a2a.a2a_service.discover_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_discover_agent(self, mock_db: object, mock_discover: AsyncMock) -> None:
        agent_id = uuid.uuid4()
        mock_discover.return_value = _mock_agent_card(
            name="discoverable", url="https://example.com/a2a"
        )
        resp = client.get(f"/api/v1/a2a/discover/{agent_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "discoverable"
        assert body["url"] == "https://example.com/a2a"
        assert "capabilities" in body
        assert "skills" in body

    @patch("app.api.a2a.a2a_service.discover_agent_card", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_discover_nonexistent_returns_404(self, mock_db: object, mock_discover: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        mock_discover.side_effect = NotFoundError("未发布")
        resp = client.get(f"/api/v1/a2a/discover/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task API 测试
# ---------------------------------------------------------------------------
class TestA2ATaskAPI:
    """A2A Task API 测试。"""

    @patch("app.api.a2a.a2a_service.create_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_create_task(self, mock_db: object, mock_create: AsyncMock) -> None:
        card_id = uuid.uuid4()
        mock_create.return_value = _mock_task(agent_card_id=card_id)
        resp = client.post("/api/v1/a2a/tasks", json={
            "agent_card_id": str(card_id),
            "input_messages": [{"role": "user", "parts": [{"type": "text/plain", "text": "hi"}]}],
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "submitted"

    @patch("app.api.a2a.a2a_service.list_tasks", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_list_tasks(self, mock_db: object, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([_mock_task()], 1)
        resp = client.get("/api/v1/a2a/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.api.a2a.a2a_service.get_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_get_task(self, mock_db: object, mock_get: AsyncMock) -> None:
        task_id = uuid.uuid4()
        mock_get.return_value = _mock_task(id=task_id, status="working")
        resp = client.get(f"/api/v1/a2a/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "working"

    @patch("app.api.a2a.a2a_service.cancel_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_cancel_task(self, mock_db: object, mock_cancel: AsyncMock) -> None:
        task_id = uuid.uuid4()
        mock_cancel.return_value = _mock_task(id=task_id, status="canceled")
        resp = client.post(f"/api/v1/a2a/tasks/{task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"

    @patch("app.api.a2a.a2a_service.cancel_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_cancel_terminal_task_returns_409(self, mock_db: object, mock_cancel: AsyncMock) -> None:
        mock_cancel.side_effect = ValueError("任务已处于终态")
        resp = client.post(f"/api/v1/a2a/tasks/{uuid.uuid4()}/cancel")
        assert resp.status_code == 409

    @patch("app.api.a2a.a2a_service.get_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_get_nonexistent_task_returns_404(self, mock_db: object, mock_get: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        mock_get.side_effect = NotFoundError("不存在")
        resp = client.get(f"/api/v1/a2a/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.a2a.a2a_service.list_tasks", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_list_tasks_empty(self, mock_db: object, mock_list: AsyncMock) -> None:
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/a2a/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @patch("app.api.a2a.a2a_service.list_tasks", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_list_tasks_filter_by_card(self, mock_db: object, mock_list: AsyncMock) -> None:
        """按 agent_card_id 过滤任务列表。"""
        card_id = uuid.uuid4()
        mock_list.return_value = ([_mock_task(agent_card_id=card_id)], 1)
        resp = client.get(f"/api/v1/a2a/tasks?agent_card_id={card_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# Task 生命周期 e2e 流程测试
# ---------------------------------------------------------------------------
class TestA2ATaskLifecycle:
    """Task 完整生命周期：创建 → 查询 → 取消。"""

    @patch("app.api.a2a.a2a_service.cancel_task", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.get_task", new_callable=AsyncMock)
    @patch("app.api.a2a.a2a_service.create_task", new_callable=AsyncMock)
    @patch("app.api.a2a.get_db")
    def test_create_get_cancel(
        self,
        mock_db: object,
        mock_create: AsyncMock,
        mock_get: AsyncMock,
        mock_cancel: AsyncMock,
    ) -> None:
        task_id = uuid.uuid4()
        card_id = uuid.uuid4()

        # 创建
        mock_create.return_value = _mock_task(id=task_id, agent_card_id=card_id, status="submitted")
        resp = client.post("/api/v1/a2a/tasks", json={
            "agent_card_id": str(card_id),
            "input_messages": [{"role": "user", "parts": [{"type": "text/plain", "text": "test"}]}],
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "submitted"

        # 查询
        mock_get.return_value = _mock_task(id=task_id, status="submitted")
        resp = client.get(f"/api/v1/a2a/tasks/{task_id}")
        assert resp.json()["status"] == "submitted"

        # 取消
        mock_cancel.return_value = _mock_task(id=task_id, status="canceled")
        resp = client.post(f"/api/v1/a2a/tasks/{task_id}/cancel")
        assert resp.json()["status"] == "canceled"


# ---------------------------------------------------------------------------
# Service 层测试
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestA2AService:
    """A2A Service 层关键逻辑测试。"""

    async def test_create_agent_card_calls_commit(self) -> None:
        from app.schemas.a2a import A2AAgentCardCreate
        from app.services.a2a import create_agent_card

        mock_db = AsyncMock()
        data = A2AAgentCardCreate(agent_id=uuid.uuid4(), name="test")
        await create_agent_card(mock_db, data)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_create_task_initial_history(self) -> None:
        """创建 Task 时包含初始历史记录。"""
        from app.schemas.a2a import A2ATaskCreate
        from app.services.a2a import create_task

        mock_db = AsyncMock()
        data = A2ATaskCreate(agent_card_id=uuid.uuid4())
        await create_task(mock_db, data)
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert added_record.status == "submitted"
        assert len(added_record.history) == 1
        assert added_record.history[0]["status"] == "submitted"

    async def test_cancel_task_terminal_raises(self) -> None:
        """取消已终态任务抛出 ValueError。"""
        from app.services.a2a import cancel_task

        mock_db = AsyncMock()
        task_record = MagicMock()
        task_record.status = "completed"
        task_record.is_deleted = False

        with patch("app.services.a2a.get_task", new_callable=AsyncMock, return_value=task_record), \
             pytest.raises(ValueError, match="终态"):
            await cancel_task(mock_db, uuid.uuid4())

    async def test_delete_agent_card_soft_delete(self) -> None:
        """删除 Agent Card 执行软删除。"""
        from app.services.a2a import delete_agent_card

        mock_db = AsyncMock()
        card_record = MagicMock()
        card_record.is_deleted = False

        with patch("app.services.a2a.get_agent_card", new_callable=AsyncMock, return_value=card_record):
            await delete_agent_card(mock_db, uuid.uuid4())
            assert card_record.is_deleted is True
            mock_db.commit.assert_awaited_once()
