"""Skill 技能系统 — Backend 层测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.skill import (
    SkillCategoryEnum,
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillSearchRequest,
    SkillUpdate,
)


# ── Schema 验证 ──────────────────────────────────────


class TestSkillSchemas:
    def test_create_valid(self) -> None:
        data = SkillCreate(
            name="my-skill",
            content="# Skill content",
        )
        assert data.name == "my-skill"
        assert data.version == "1.0.0"
        assert data.category == SkillCategoryEnum.CUSTOM
        assert data.tags == []
        assert data.applicable_agents == []

    def test_create_full(self) -> None:
        data = SkillCreate(
            name="code-review",
            version="2.0.0",
            description="代码审查技能",
            content="# Review",
            category=SkillCategoryEnum.PUBLIC,
            tags=["review"],
            applicable_agents=["agent-a"],
            author="cky",
            metadata={"key": "value"},
        )
        assert data.category == SkillCategoryEnum.PUBLIC
        assert data.tags == ["review"]

    def test_create_invalid_name(self) -> None:
        with pytest.raises(Exception):
            SkillCreate(name="UPPER CASE!", content="x")

    def test_create_empty_name(self) -> None:
        with pytest.raises(Exception):
            SkillCreate(name="", content="x")

    def test_create_empty_content(self) -> None:
        with pytest.raises(Exception):
            SkillCreate(name="ok", content="")

    def test_update_partial(self) -> None:
        data = SkillUpdate(version="3.0.0")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"version": "3.0.0"}

    def test_search_valid(self) -> None:
        data = SkillSearchRequest(query="test", limit=10)
        assert data.query == "test"
        assert data.category is None

    def test_search_with_category(self) -> None:
        data = SkillSearchRequest(query="test", category=SkillCategoryEnum.PUBLIC)
        assert data.category == SkillCategoryEnum.PUBLIC

    def test_response_from_attributes(self) -> None:
        """SkillResponse 可从 ORM 对象构建。"""
        now = datetime.now(timezone.utc)
        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.name = "test"
        mock_record.version = "1.0.0"
        mock_record.description = "desc"
        mock_record.content = "content"
        mock_record.category = "custom"
        mock_record.tags = ["t1"]
        mock_record.applicable_agents = []
        mock_record.author = "a"
        mock_record.metadata_ = {"k": "v"}
        mock_record.created_at = now
        mock_record.updated_at = now
        resp = SkillResponse.model_validate(mock_record, from_attributes=True)
        assert resp.name == "test"
        assert resp.metadata == {"k": "v"}

    def test_list_response(self) -> None:
        lr = SkillListResponse(data=[], total=0)
        assert lr.total == 0

    def test_category_enum(self) -> None:
        assert SkillCategoryEnum.PUBLIC.value == "public"
        assert SkillCategoryEnum.CUSTOM.value == "custom"


# ── API 端点 ─────────────────────────────────────────


def _make_skill_dict(**overrides):
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "id": str(uuid.uuid4()),
        "name": "test-skill",
        "version": "1.0.0",
        "description": "desc",
        "content": "# content",
        "category": "custom",
        "tags": [],
        "applicable_agents": [],
        "author": "",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _make_mock_record(**overrides):
    d = _make_skill_dict(**overrides)
    mock = MagicMock()
    for k, v in d.items():
        setattr(mock, k, v)
    if "id" in d and isinstance(d["id"], str):
        mock.id = uuid.UUID(d["id"])
    return mock


class TestSkillAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_create(self, mock_db, mock_svc) -> None:
        record = _make_mock_record(name="new-skill")
        mock_svc.create_skill = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/skills", json={
            "name": "new-skill",
            "content": "# New",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "new-skill"

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_list(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.list_skills = AsyncMock(return_value=([record], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["data"]) == 1

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_get(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.get_skill = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.get(f"/api/v1/skills/{record.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-skill"

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_update(self, mock_db, mock_svc) -> None:
        record = _make_mock_record(version="2.0.0")
        mock_svc.update_skill = AsyncMock(return_value=record)
        mock_db.return_value = AsyncMock()
        resp = self.client.put(f"/api/v1/skills/{record.id}", json={
            "version": "2.0.0",
        })
        assert resp.status_code == 200
        assert resp.json()["version"] == "2.0.0"

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_delete(self, mock_db, mock_svc) -> None:
        mock_svc.delete_skill = AsyncMock(return_value=None)
        mock_db.return_value = AsyncMock()
        skill_id = uuid.uuid4()
        resp = self.client.delete(f"/api/v1/skills/{skill_id}")
        assert resp.status_code == 204

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_search(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.search_skills = AsyncMock(return_value=[record])
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/skills/search", json={
            "query": "test",
        })
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @patch("app.api.skills.skill_service")
    @patch("app.api.skills.get_db")
    def test_find_for_agent(self, mock_db, mock_svc) -> None:
        record = _make_mock_record()
        mock_svc.find_skills_for_agent = AsyncMock(return_value=[record])
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/skills/for-agent/my-agent")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── Service 逻辑 ─────────────────────────────────────


class TestSkillService:
    def test_escape_like(self) -> None:
        from app.services.skill import _escape_like
        assert _escape_like("hello%world_!") == "hello\\%world\\_!"
        assert _escape_like("normal") == "normal"
