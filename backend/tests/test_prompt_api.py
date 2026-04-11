"""Prompt API 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestPromptAPI:
    """Prompt 模板 API 测试。"""

    @patch("app.api.prompt.prompt_service")
    @patch("app.api.prompt.agent_service")
    def test_preview_success(
        self,
        mock_agent_service: MagicMock,
        mock_prompt_service: MagicMock,
        client: TestClient,
    ) -> None:
        mock_agent = MagicMock()
        mock_agent.instructions = "你是{{role}}"
        mock_agent.prompt_variables = [{"name": "role", "type": "string", "default": "助手"}]
        mock_agent_service.get_agent_by_name = AsyncMock(return_value=mock_agent)
        mock_prompt_service.preview_prompt.return_value = {
            "rendered": "你是审查员",
            "warnings": [],
        }

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents/demo/prompt/preview", json={"variables": {"role": "审查员"}})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["rendered"] == "你是审查员"
        assert body["warnings"] == []

    @patch("app.api.prompt.prompt_service")
    @patch("app.api.prompt.agent_service")
    def test_validate_success(
        self,
        mock_agent_service: MagicMock,
        mock_prompt_service: MagicMock,
        client: TestClient,
    ) -> None:
        mock_agent_service.get_agent_by_name = AsyncMock(return_value=MagicMock())
        mock_prompt_service.validate_prompt.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "referenced_variables": ["role"],
        }

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post(
                "/api/v1/agents/demo/prompt/validate",
                json={
                    "instructions": "你是{{role}}",
                    "variables": [{"name": "role", "type": "string", "required": True}],
                },
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["referenced_variables"] == ["role"]


# 延迟导入避免循环依赖
from app.core.database import get_db as get_db_original  # noqa: E402
