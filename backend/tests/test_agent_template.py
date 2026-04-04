"""Agent 模板 — Backend 层测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.agent_template import (
    AgentTemplateCreate,
    AgentTemplateListResponse,
    AgentTemplateResponse,
    AgentTemplateUpdate,
    CreateAgentFromTemplate,
)


# ── Schema 验证 ──────────────────────────────────────


class TestAgentTemplateSchemas:
    def test_create_minimal(self) -> None:
        data = AgentTemplateCreate(
            name="my-template",
            display_name="My Template",
        )
        assert data.name == "my-template"
        assert data.category == "general"
        assert data.config == {}

    def test_create_full(self) -> None:
        data = AgentTemplateCreate(
            name="code-review",
            display_name="代码审查模板",
            description="专业代码审查 Agent",
            category="development",
            icon="CodeOutlined",
            config={"instructions": "..."},
            metadata={"priority": 1},
        )
        assert data.category == "development"
        assert data.config["instructions"] == "..."

    def test_create_invalid_name(self) -> None:
        with pytest.raises(Exception):
            AgentTemplateCreate(name="INVALID!", display_name="x")

    def test_update_partial(self) -> None:
        data = AgentTemplateUpdate(description="new desc")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"description": "new desc"}

    def test_create_from_template(self) -> None:
        data = CreateAgentFromTemplate(agent_name="new-agent")
        assert data.overrides == {}

    def test_response_from_attributes(self) -> None:
        now = datetime.now(timezone.utc)
        mock = MagicMock()
        mock.id = uuid.uuid4()
        mock.name = "test"
        mock.display_name = "Test"
        mock.description = "desc"
        mock.category = "general"
        mock.icon = "RobotOutlined"
        mock.config = {}
        mock.is_builtin = True
        mock.metadata_ = {}
        mock.created_at = now
        mock.updated_at = now
        resp = AgentTemplateResponse.model_validate(mock, from_attributes=True)
        assert resp.name == "test"
        assert resp.is_builtin is True

    def test_list_response(self) -> None:
        lr = AgentTemplateListResponse(data=[], total=0)
        assert lr.total == 0


# ── API 端点 ─────────────────────────────────────────


def _make_mock_record(**overrides):
    now = datetime.now(timezone.utc)
    d = {
        "id": uuid.uuid4(),
        "name": "test-template",
        "display_name": "Test Template",
        "description": "desc",
        "category": "general",
        "icon": "RobotOutlined",
        "config": {"instructions": "hello"},
        "is_builtin": False,
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    mock = MagicMock()
    for k, v in d.items():
        setattr(mock, k, v)
    return mock


class TestAgentTemplateAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_create(self, mock_db, mock_svc) -> None:
        record = _make_mock_record(name="new-tpl")
        mock_svc.create_template = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/agent-templates", json={
            "name": "new-tpl",
            "display_name": "New Template",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "new-tpl"

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_list(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.list_templates = AsyncMock(return_value=([record], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/agent-templates")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_get(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.get_template = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.get(f"/api/v1/agent-templates/{record.id}")
        assert resp.status_code == 200

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_update(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.update_template = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.put(f"/api/v1/agent-templates/{record.id}", json={"description": "updated"})
        assert resp.status_code == 200

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_update_builtin_rejected(self, mock_db, mock_svc) -> None:
        mock_svc.update_template = AsyncMock(side_effect=ValueError("内置模板不可编辑"))
        mock_db.return_value = AsyncMock()
        resp = self.client.put(f"/api/v1/agent-templates/{uuid.uuid4()}", json={"description": "x"})
        assert resp.status_code == 403

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_delete(self, mock_db, mock_svc) -> None:
        mock_svc.delete_template = AsyncMock(return_value=None)
        mock_db.return_value = AsyncMock()
        resp = self.client.delete(f"/api/v1/agent-templates/{uuid.uuid4()}")
        assert resp.status_code == 204

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_delete_builtin_rejected(self, mock_db, mock_svc) -> None:
        mock_svc.delete_template = AsyncMock(side_effect=ValueError("内置模板不可删除"))
        mock_db.return_value = AsyncMock()
        resp = self.client.delete(f"/api/v1/agent-templates/{uuid.uuid4()}")
        assert resp.status_code == 403

    @patch("app.api.agent_templates.template_service")
    @patch("app.api.agent_templates.get_db")
    def test_seed(self, mock_db, mock_svc) -> None:
        mock_svc.seed_builtin_templates = AsyncMock(return_value=10)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/agent-templates/seed")
        assert resp.status_code == 200
        assert resp.json()["created"] == 10


# ── Service 逻辑 ─────────────────────────────────────


class TestAgentTemplateService:
    def test_builtin_templates_count(self) -> None:
        from app.services.agent_template import BUILTIN_TEMPLATES
        assert len(BUILTIN_TEMPLATES) == 14

    def test_builtin_templates_names(self) -> None:
        from app.services.agent_template import BUILTIN_TEMPLATES
        names = {t["name"] for t in BUILTIN_TEMPLATES}
        expected = {
            "triage", "faq-bot", "researcher", "data-analyst", "report-writer",
            "code-assistant", "translator", "customer-service", "summarizer", "coordinator",
        }
        expected = {
            "triage", "faq-bot", "researcher", "data-analyst", "report-writer",
            "code-assistant", "translator", "customer-service", "summarizer", "coordinator",
            # 垂直 Agent
            "code-reviewer", "devops-assistant", "bi-analyst", "complaint-handler",
        }
        assert names == expected

    def test_builtin_templates_have_config(self) -> None:
        from app.services.agent_template import BUILTIN_TEMPLATES
        for tpl in BUILTIN_TEMPLATES:
            assert "instructions" in tpl["config"], f"{tpl['name']} 缺少 instructions"
