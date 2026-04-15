"""Marketplace 全栈测试 — Schema / API / Service / Router。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.marketplace import (
    InstallTemplateRequest,
    MarketplaceListResponse,
    MarketplaceTemplateResponse,
    PublishTemplateRequest,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)

now = datetime.now(UTC)
TPL_ID = uuid.uuid4()
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_tpl(**overrides: object) -> MagicMock:
    """构造 AgentTemplate mock 对象。"""
    d: dict[str, object] = {
        "id": TPL_ID,
        "name": "test-tpl",
        "display_name": "Test Template",
        "description": "desc",
        "category": "general",
        "icon": "robot",
        "published": True,
        "downloads": 10,
        "rating": 4.5,
        "rating_count": 2,
        "author_org_id": None,
        "is_builtin": False,
        "config": {"instructions": "hello"},
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_review(**overrides: object) -> MagicMock:
    """构造 MarketplaceReview mock 对象。"""
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "template_id": TPL_ID,
        "user_id": USER_ID,
        "score": 5,
        "comment": "Great!",
        "is_deleted": False,
        "created_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


# ──────────────────────────────────────────────
# Schema 测试
# ──────────────────────────────────────────────

class TestMarketplaceSchemas:
    """Marketplace Pydantic 模型测试。"""

    def test_template_response_from_attributes(self) -> None:
        tpl = _make_tpl()
        resp = MarketplaceTemplateResponse.model_validate(tpl)
        assert resp.id == TPL_ID
        assert resp.published is True
        assert resp.downloads == 10
        assert resp.rating == 4.5

    def test_list_response(self) -> None:
        tpl = _make_tpl()
        lr = MarketplaceListResponse(
            data=[MarketplaceTemplateResponse.model_validate(tpl)],
            total=1, limit=20, offset=0,
        )
        assert len(lr.data) == 1
        assert lr.total == 1

    def test_publish_request(self) -> None:
        req = PublishTemplateRequest(template_id=TPL_ID)
        assert req.template_id == TPL_ID

    def test_install_request_minimal(self) -> None:
        req = InstallTemplateRequest(agent_name="my-agent")
        assert req.agent_name == "my-agent"
        assert req.overrides == {}

    def test_install_request_name_too_short(self) -> None:
        with pytest.raises(ValidationError):
            InstallTemplateRequest(agent_name="ab")

    def test_review_create_valid(self) -> None:
        rc = ReviewCreate(score=4, comment="nice")
        assert rc.score == 4

    def test_review_create_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            ReviewCreate(score=0)
        with pytest.raises(ValidationError):
            ReviewCreate(score=6)

    def test_review_response_from_attributes(self) -> None:
        review = _make_review()
        resp = ReviewResponse.model_validate(review)
        assert resp.score == 5

    def test_review_list_response(self) -> None:
        review = _make_review()
        lr = ReviewListResponse(
            data=[ReviewResponse.model_validate(review)],
            total=1,
        )
        assert lr.total == 1


# ──────────────────────────────────────────────
# API 测试
# ──────────────────────────────────────────────

class TestMarketplaceAPI:
    """Marketplace REST API 端点测试。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_browse_marketplace(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        tpl = _make_tpl()
        mock_svc.list_marketplace = AsyncMock(return_value=([tpl], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/marketplace")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["name"] == "test-tpl"

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_browse_with_filters(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.list_marketplace = AsyncMock(return_value=([], 0))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/marketplace?category=general&search=test&sort_by=rating")
        assert resp.status_code == 200
        mock_svc.list_marketplace.assert_called_once()

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_get_marketplace_template(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        tpl = _make_tpl()
        mock_svc.get_marketplace_template = AsyncMock(return_value=tpl)
        mock_db.return_value = AsyncMock()
        resp = self.client.get(f"/api/v1/marketplace/{TPL_ID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(TPL_ID)

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_publish_template(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        tpl = _make_tpl(published=True)
        mock_svc.publish_template = AsyncMock(return_value=tpl)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/marketplace/publish", json={"template_id": str(TPL_ID)})
        assert resp.status_code == 200
        assert resp.json()["published"] is True

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_unpublish_template(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        tpl = _make_tpl(published=False)
        mock_svc.unpublish_template = AsyncMock(return_value=tpl)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/marketplace/unpublish", json={"template_id": str(TPL_ID)})
        assert resp.status_code == 200
        assert resp.json()["published"] is False

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_install_template(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.install_template = AsyncMock(return_value={"instructions": "hello"})
        mock_db.return_value = AsyncMock()
        resp = self.client.post(
            f"/api/v1/marketplace/{TPL_ID}/install",
            json={"agent_name": "new-agent"},
        )
        assert resp.status_code == 200
        assert "config" in resp.json()

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_submit_review(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        review = _make_review()
        mock_svc.create_review = AsyncMock(return_value=review)
        mock_db.return_value = AsyncMock()
        resp = self.client.post(
            f"/api/v1/marketplace/{TPL_ID}/reviews",
            json={"score": 5, "comment": "Great!"},
        )
        assert resp.status_code == 201
        assert resp.json()["score"] == 5

    @patch("app.api.marketplace.mp_svc")
    @patch("app.api.marketplace.get_db")
    def test_list_reviews(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        review = _make_review()
        mock_svc.list_reviews = AsyncMock(return_value=([review], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get(f"/api/v1/marketplace/{TPL_ID}/reviews")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ──────────────────────────────────────────────
# Service 测试
# ──────────────────────────────────────────────

class TestMarketplaceService:
    """Marketplace Service 异步逻辑测试。"""

    @pytest.fixture()
    def db(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_publish_template_success(self, db: AsyncMock) -> None:
        from app.services.marketplace import publish_template

        tpl = _make_tpl(published=False)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = tpl
        db.execute = AsyncMock(return_value=execute_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await publish_template(db, TPL_ID)
        assert result.published is True

    @pytest.mark.asyncio
    async def test_publish_already_published_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import ConflictError
        from app.services.marketplace import publish_template

        tpl = _make_tpl(published=True)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = tpl
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(ConflictError, match="已发布"):
            await publish_template(db, TPL_ID)

    @pytest.mark.asyncio
    async def test_unpublish_not_published_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import ConflictError
        from app.services.marketplace import unpublish_template

        tpl = _make_tpl(published=False)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = tpl
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(ConflictError, match="未发布"):
            await unpublish_template(db, TPL_ID)

    @pytest.mark.asyncio
    async def test_install_unpublished_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import ValidationError as VE
        from app.services.marketplace import install_template

        tpl = _make_tpl(published=False)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = tpl
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(VE, match="未发布"):
            await install_template(db, TPL_ID)

    @pytest.mark.asyncio
    async def test_create_review_duplicate_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import ConflictError
        from app.services.marketplace import create_review

        tpl = _make_tpl(published=True)
        existing_review = _make_review()

        call_count = 0

        async def _side_effect(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # _get_template query
                result.scalar_one_or_none.return_value = tpl
            else:
                # duplicate check query
                result.scalar_one_or_none.return_value = existing_review
            return result

        db.execute = AsyncMock(side_effect=_side_effect)

        with pytest.raises(ConflictError, match="已评价"):
            await create_review(db, TPL_ID, USER_ID, 5, "again")

    @pytest.mark.asyncio
    async def test_get_template_not_found_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.marketplace import get_marketplace_template

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(NotFoundError):
            await get_marketplace_template(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_unpublished_template_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.marketplace import get_marketplace_template

        tpl = _make_tpl(published=False)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = tpl
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(NotFoundError, match="未发布"):
            await get_marketplace_template(db, TPL_ID)


# ──────────────────────────────────────────────
# Router 注册测试
# ──────────────────────────────────────────────

class TestMarketplaceRouter:
    """验证路由注册。"""

    def test_router_has_expected_routes(self) -> None:
        from app.api.marketplace import router

        paths = [r.path for r in router.routes]
        assert "/api/v1/marketplace" in paths
        assert "/api/v1/marketplace/{template_id}" in paths
        assert "/api/v1/marketplace/publish" in paths
        assert "/api/v1/marketplace/unpublish" in paths
        assert "/api/v1/marketplace/{template_id}/install" in paths
        assert "/api/v1/marketplace/{template_id}/reviews" in paths

    def test_router_registered_in_app(self) -> None:
        from app.main import app

        paths = [r.path for r in app.routes]
        assert "/api/v1/marketplace" in paths
