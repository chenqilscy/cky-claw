"""Environment API 单元测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _mock_env(name: str = "dev") -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.name = name
    m.display_name = "开发"
    m.description = ""
    m.color = "#52c41a"
    m.sort_order = 0
    m.is_protected = False
    m.settings_override = {}
    m.org_id = None
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _mock_binding() -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.agent_config_id = uuid.uuid4()
    m.environment_id = uuid.uuid4()
    m.version_id = uuid.uuid4()
    m.is_active = True
    m.published_at = datetime.now(UTC)
    m.published_by = None
    m.rollback_from_id = None
    m.notes = "发布"
    m.org_id = None
    return m


class TestEnvironmentAPI:
    """环境管理 API 测试。"""

    @patch("app.api.environments.environment_service")
    def test_list_environments(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_environments = AsyncMock(return_value=[_mock_env("dev"), _mock_env("staging")])

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/environments")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    @patch("app.api.environments.environment_service")
    def test_publish_agent(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.publish_agent = AsyncMock(return_value=_mock_binding())

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.post(
                "/api/v1/environments/dev/agents/demo/publish",
                json={"notes": "发布到开发环境"},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "id" in resp.json()

    @patch("app.api.environments.environment_service")
    def test_diff_environments(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.diff_environments = AsyncMock(return_value=({"instructions": "a"}, {"instructions": "b"}))

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_original] = lambda: mock_session
        try:
            resp = client.get("/api/v1/environments/diff?agent=demo&env1=staging&env2=prod")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["snapshot_env1"]["instructions"] == "a"
        assert body["snapshot_env2"]["instructions"] == "b"


# 延迟导入避免循环依赖
from app.core.database import get_db as get_db_original  # noqa: E402
