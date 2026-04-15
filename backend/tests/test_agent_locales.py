"""Agent 多语言 Instructions API 单元测试。

使用 mock service 层 + TestClient 进行端点测试。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.main import app
from app.schemas.agent_locale import AgentLocaleCreate, AgentLocaleResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_locale_record(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造模拟 AgentLocale ORM 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "locale": "zh-CN",
        "instructions": "你是一个测试助手。",
        "is_default": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestAgentLocaleSchemas:
    """Pydantic Schema 校验。"""

    def test_create_valid_locale(self) -> None:
        data = AgentLocaleCreate(locale="zh-CN", instructions="你好")
        assert data.locale == "zh-CN"

    def test_create_valid_locale_en(self) -> None:
        data = AgentLocaleCreate(locale="en-US", instructions="Hello")
        assert data.locale == "en-US"

    def test_create_valid_locale_bare(self) -> None:
        data = AgentLocaleCreate(locale="ja", instructions="こんにちは")
        assert data.locale == "ja"

    def test_create_invalid_locale_format(self) -> None:
        with pytest.raises(ValueError, match="locale 格式无效"):
            AgentLocaleCreate(locale="invalid!", instructions="test")

    def test_create_invalid_locale_too_long(self) -> None:
        with pytest.raises(ValueError):
            AgentLocaleCreate(locale="x" * 20, instructions="test")

    def test_response_from_orm(self) -> None:
        mock = _make_locale_record()
        resp = AgentLocaleResponse.model_validate(mock, from_attributes=True)
        assert resp.locale == "zh-CN"
        assert resp.is_default is True


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestAgentLocaleAPI:
    """Agent Locale CRUD API 端点测试。"""

    @patch("app.api.agent_locales.locale_service")
    def test_list_locales_empty(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_locales = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents/test-agent/locales")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @patch("app.api.agent_locales.locale_service")
    def test_list_locales_with_data(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.list_locales = AsyncMock(return_value=[
            _make_locale_record(locale="zh-CN", is_default=True),
            _make_locale_record(locale="en-US", is_default=False),
        ])
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.get("/api/v1/agents/test-agent/locales")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["locale"] == "zh-CN"

    @patch("app.api.agent_locales.locale_service")
    def test_create_locale_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.create_locale = AsyncMock(return_value=_make_locale_record(
            locale="en-US", instructions="Hello", is_default=False
        ))
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents/test-agent/locales", json={
                "locale": "en-US",
                "instructions": "Hello",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        assert resp.json()["locale"] == "en-US"

    @patch("app.api.agent_locales.locale_service")
    def test_create_locale_conflict(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.create_locale = AsyncMock(
            side_effect=ConflictError("locale 'zh-CN' 已存在")
        )
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents/test-agent/locales", json={
                "locale": "zh-CN",
                "instructions": "重复",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 409

    @patch("app.api.agent_locales.locale_service")
    def test_create_locale_agent_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.create_locale = AsyncMock(
            side_effect=NotFoundError("Agent 'no-exist' 不存在")
        )
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents/no-exist/locales", json={
                "locale": "en-US",
                "instructions": "test",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    @patch("app.api.agent_locales.locale_service")
    def test_update_locale_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.update_locale = AsyncMock(return_value=_make_locale_record(
            locale="zh-CN", instructions="更新后的指令"
        ))
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.put("/api/v1/agents/test-agent/locales/zh-CN", json={
                "instructions": "更新后的指令",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["instructions"] == "更新后的指令"

    @patch("app.api.agent_locales.locale_service")
    def test_update_locale_not_found(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.update_locale = AsyncMock(
            side_effect=NotFoundError("语言版本 'fr-FR' 不存在")
        )
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.put("/api/v1/agents/test-agent/locales/fr-FR", json={
                "instructions": "Bonjour",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    @patch("app.api.agent_locales.locale_service")
    def test_delete_locale_success(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_locale = AsyncMock(return_value=None)
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.delete("/api/v1/agents/test-agent/locales/en-US")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 204

    @patch("app.api.agent_locales.locale_service")
    def test_delete_default_locale_rejected(self, mock_svc: MagicMock, client: TestClient) -> None:
        mock_svc.delete_locale = AsyncMock(
            side_effect=ValidationError("默认语言版本不可删除，请先切换默认语言")
        )
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.delete("/api/v1/agents/test-agent/locales/zh-CN")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_create_locale_invalid_body(self, client: TestClient) -> None:
        """请求体缺少必填字段。"""
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.post("/api/v1/agents/test-agent/locales", json={})
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    @patch("app.api.agent_locales.locale_service")
    def test_update_remove_only_default_rejected(self, mock_svc: MagicMock, client: TestClient) -> None:
        """取消唯一默认语言版本应返回 422。"""
        mock_svc.update_locale = AsyncMock(
            side_effect=ValidationError("不可取消唯一的默认语言版本")
        )
        mock_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.put("/api/v1/agents/test-agent/locales/zh-CN", json={
                "instructions": "测试",
                "is_default": False,
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422
