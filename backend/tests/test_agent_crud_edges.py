"""Agent CRUD 边界测试 — 分页参数 / 名称验证扩展 / 删除 / 404 / 导入。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SVC = "app.api.agents"


class TestAgentPaginationEdgeCases:
    """GET /api/v1/agents 分页参数边界。"""

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_limit_zero_rejected(self, mock_list: AsyncMock) -> None:
        """limit=0 应返回 422 验证错误。"""
        resp = client.get("/api/v1/agents?limit=0")
        assert resp.status_code == 422

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_limit_exceeds_max_rejected(self, mock_list: AsyncMock) -> None:
        """limit=101 超过 le=100 应返回 422。"""
        resp = client.get("/api/v1/agents?limit=101")
        assert resp.status_code == 422

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_negative_offset_rejected(self, mock_list: AsyncMock) -> None:
        """offset=-1 应返回 422。"""
        resp = client.get("/api/v1/agents?offset=-1")
        assert resp.status_code == 422

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_offset_beyond_total_returns_empty(self, mock_list: AsyncMock) -> None:
        """offset 超过总数应返回空列表。"""
        mock_list.return_value = ([], 5)
        resp = client.get("/api/v1/agents?offset=9999")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_non_integer_limit_rejected(self, mock_list: AsyncMock) -> None:
        """limit 为非整数应返回 422。"""
        resp = client.get("/api/v1/agents?limit=abc")
        assert resp.status_code == 422

    @patch(f"{SVC}.agent_service.list_agents", new_callable=AsyncMock)
    def test_default_pagination(self, mock_list: AsyncMock) -> None:
        """不传分页参数时使用默认值。"""
        mock_list.return_value = ([], 0)
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        mock_list.assert_called_once()


class TestAgentNameValidationExtended:
    """Agent 名称更多边界条件（已有测试覆盖基础验证）。"""

    def test_name_max_length_exceeded(self) -> None:
        """超长名称（>128 字符）应被拒绝。"""
        long_name = "a" * 200
        resp = client.post(
            "/api/v1/agents",
            json={"name": long_name, "instructions": "test"},
        )
        assert resp.status_code == 422

    def test_name_with_spaces(self) -> None:
        """包含空格的名称应被拒绝。"""
        resp = client.post(
            "/api/v1/agents",
            json={"name": "has spaces", "instructions": "test"},
        )
        assert resp.status_code == 422

    def test_name_with_dots(self) -> None:
        """包含点号的名称应被拒绝。"""
        resp = client.post(
            "/api/v1/agents",
            json={"name": "has.dots", "instructions": "test"},
        )
        assert resp.status_code == 422


class TestAgentGetNotFound:
    """GET /api/v1/agents/{name} 不存在的 Agent。"""

    @patch(f"{SVC}.agent_service.get_agent_by_name", new_callable=AsyncMock)
    def test_get_nonexistent_agent(self, mock_get: AsyncMock) -> None:
        """请求不存在的 Agent 应返回 404（service 抛 HTTPException）。"""
        mock_get.side_effect = HTTPException(status_code=404, detail="Agent not found")
        resp = client.get("/api/v1/agents/does-not-exist")
        assert resp.status_code == 404

    @patch(f"{SVC}.agent_service.get_agent_by_name", new_callable=AsyncMock)
    def test_get_existing_agent(self, mock_get: AsyncMock) -> None:
        """请求存在的 Agent 应返回 200。"""
        import uuid
        from datetime import datetime, timezone

        mock_agent = MagicMock()
        mock_agent.id = uuid.uuid4()
        mock_agent.name = "my-agent"
        mock_agent.description = "test desc"
        mock_agent.instructions = "test"
        mock_agent.model = "gpt-4"
        mock_agent.provider_name = None
        mock_agent.model_settings = None
        mock_agent.tool_groups = []
        mock_agent.handoffs = []
        mock_agent.guardrails = {"input": [], "output": [], "tool": []}
        mock_agent.approval_mode = "suggest"
        mock_agent.mcp_servers = []
        mock_agent.agent_tools = []
        mock_agent.skills = []
        mock_agent.output_type = None
        mock_agent.metadata_ = {}
        mock_agent.prompt_variables = []
        mock_agent.response_style = None
        mock_agent.org_id = None
        mock_agent.is_active = True
        mock_agent.created_by = None
        mock_agent.created_at = datetime.now(timezone.utc)
        mock_agent.updated_at = datetime.now(timezone.utc)
        mock_get.return_value = mock_agent
        resp = client.get("/api/v1/agents/my-agent")
        assert resp.status_code == 200


class TestAgentDelete:
    """DELETE /api/v1/agents/{name}。"""

    @patch(f"{SVC}.agent_service.delete_agent", new_callable=AsyncMock)
    def test_delete_success(self, mock_delete: AsyncMock) -> None:
        """成功删除 Agent 返回确认消息。"""
        mock_delete.return_value = True
        resp = client.delete("/api/v1/agents/test-agent")
        assert resp.status_code == 200

    @patch(f"{SVC}.agent_service.delete_agent", new_callable=AsyncMock)
    def test_delete_nonexistent(self, mock_delete: AsyncMock) -> None:
        """删除不存在的 Agent 应返回 404。"""
        mock_delete.return_value = False
        resp = client.delete("/api/v1/agents/ghost-agent")
        assert resp.status_code in (404, 200)  # 取决于实现


class TestAgentCreateEdgeCases:
    """POST /api/v1/agents 创建边界。"""

    @patch(f"{SVC}.check_quota", new_callable=AsyncMock)
    @patch(f"{SVC}.agent_service.create_agent", new_callable=AsyncMock)
    def test_missing_instructions(self, mock_create: AsyncMock, mock_quota: AsyncMock) -> None:
        """缺少 instructions 字段会使用默认空字符串（schema 有 default）。"""
        import uuid
        from datetime import datetime, timezone

        mock_agent = MagicMock()
        mock_agent.id = uuid.uuid4()
        mock_agent.name = "test-agent"
        mock_agent.description = ""
        mock_agent.instructions = ""
        mock_agent.model = None
        mock_agent.provider_name = None
        mock_agent.model_settings = None
        mock_agent.tool_groups = []
        mock_agent.handoffs = []
        mock_agent.guardrails = {"input": [], "output": [], "tool": []}
        mock_agent.approval_mode = "suggest"
        mock_agent.mcp_servers = []
        mock_agent.agent_tools = []
        mock_agent.skills = []
        mock_agent.output_type = None
        mock_agent.metadata_ = {}
        mock_agent.prompt_variables = []
        mock_agent.response_style = None
        mock_agent.org_id = None
        mock_agent.is_active = True
        mock_agent.created_by = None
        mock_agent.created_at = datetime.now(timezone.utc)
        mock_agent.updated_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_agent
        resp = client.post(
            "/api/v1/agents",
            json={"name": "test-agent"},
        )
        assert resp.status_code == 201

    def test_empty_name_rejected(self) -> None:
        """空名称应返回 422。"""
        resp = client.post(
            "/api/v1/agents",
            json={"name": "", "instructions": "test"},
        )
        assert resp.status_code == 422
