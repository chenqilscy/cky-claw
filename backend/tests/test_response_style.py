"""response_style 字段集成测试（Schema + API）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse


SVC = "app.services.agent"
TENANT = "app.api.agents"
client = TestClient(app)


def _make_agent_config(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造模拟 AgentConfig ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "style-agent",
        "description": "",
        "instructions": "test",
        "model": "gpt-4o",
        "provider_name": None,
        "model_settings": None,
        "tool_groups": [],
        "handoffs": [],
        "guardrails": {"input": [], "output": [], "tool": []},
        "approval_mode": "suggest",
        "mcp_servers": [],
        "agent_tools": [],
        "skills": [],
        "output_type": None,
        "metadata_": {},
        "prompt_variables": [],
        "response_style": None,
        "org_id": None,
        "is_active": True,
        "created_by": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestResponseStyleSchema:
    """Schema 验证。"""

    def test_create_default_none(self) -> None:
        """AgentCreate 默认 response_style 为 None。"""
        data = AgentCreate(name="test-abc")
        assert data.response_style is None

    def test_create_concise(self) -> None:
        """允许设置 concise。"""
        data = AgentCreate(name="test-abc", response_style="concise")
        assert data.response_style == "concise"

    def test_create_invalid_style(self) -> None:
        """不允许的 style 报错。"""
        with pytest.raises(Exception):
            AgentCreate(name="test-abc", response_style="invalid-style")

    def test_update_response_style(self) -> None:
        """AgentUpdate 允许 response_style。"""
        data = AgentUpdate(response_style="concise")
        assert data.response_style == "concise"

    def test_response_includes_field(self) -> None:
        """AgentResponse 包含 response_style。"""
        mock = _make_agent_config(response_style="concise")
        resp = AgentResponse.model_validate(mock, from_attributes=True)
        assert resp.response_style == "concise"

    def test_response_null_style(self) -> None:
        """AgentResponse 允许 null response_style。"""
        mock = _make_agent_config()
        resp = AgentResponse.model_validate(mock, from_attributes=True)
        assert resp.response_style is None


class TestResponseStyleAPI:
    """API 端点。"""

    @patch(f"{TENANT}.check_quota", new_callable=AsyncMock)
    @patch(f"{SVC}.create_agent", new_callable=AsyncMock)
    def test_create_with_response_style(self, mock_create: AsyncMock, mock_quota: AsyncMock) -> None:
        """创建 Agent 时传递 response_style。"""
        mock_create.return_value = _make_agent_config(response_style="concise")
        resp = client.post(
            "/api/v1/agents",
            json={"name": "style-agent", "response_style": "concise"},
        )
        assert resp.status_code == 201
        assert resp.json()["response_style"] == "concise"

    @patch(f"{TENANT}.check_quota", new_callable=AsyncMock)
    @patch(f"{SVC}.create_agent", new_callable=AsyncMock)
    def test_create_without_response_style(self, mock_create: AsyncMock, mock_quota: AsyncMock) -> None:
        """不传 response_style 时默认 null。"""
        mock_create.return_value = _make_agent_config()
        resp = client.post(
            "/api/v1/agents",
            json={"name": "style-agent"},
        )
        assert resp.status_code == 201
        assert resp.json()["response_style"] is None

    @patch(f"{SVC}.get_agent_by_name", new_callable=AsyncMock)
    @patch(f"{SVC}.update_agent", new_callable=AsyncMock)
    def test_update_response_style(self, mock_update: AsyncMock, mock_get: AsyncMock) -> None:
        """更新 Agent 的 response_style。"""
        mock_get.return_value = _make_agent_config()
        mock_update.return_value = _make_agent_config(response_style="concise")
        resp = client.put(
            "/api/v1/agents/style-agent",
            json={"response_style": "concise"},
        )
        assert resp.status_code == 200
        assert resp.json()["response_style"] == "concise"
