"""成本路由 API 测试。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


def _make_provider_orm(**overrides: object) -> MagicMock:
    """构造 ProviderConfig ORM mock。"""
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "test-gpt4",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_encrypted": "gAAAAABk...",
        "auth_type": "api_key",
        "is_enabled": True,
        "is_deleted": False,
        "model_tier": "moderate",
        "capabilities": ["text", "code"],
        "org_id": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _mock_db_session(*providers: MagicMock) -> AsyncMock:
    """构造异步 DB session mock，execute 返回指定 providers。"""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(providers)
    session.execute = AsyncMock(return_value=result)
    return session


# ═══════════════════════════════════════════════════════════════════
# /classify 端点
# ═══════════════════════════════════════════════════════════════════


class TestClassifyEndpoint:
    """POST /api/v1/cost-router/classify 端点测试。"""

    def test_classify_simple(self, client: TestClient) -> None:
        """短文本 → simple。"""
        resp = client.post("/api/v1/cost-router/classify", json={"text": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "simple"
        assert data["text_length"] == 2

    def test_classify_complex(self, client: TestClient) -> None:
        """含代码关键词 → complex。"""
        resp = client.post("/api/v1/cost-router/classify", json={"text": "请帮我写一段代码"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "complex"

    def test_classify_reasoning(self, client: TestClient) -> None:
        """含推理关键词 → reasoning。"""
        resp = client.post("/api/v1/cost-router/classify", json={"text": "请帮我证明数学定理"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "reasoning"

    def test_classify_multimodal(self, client: TestClient) -> None:
        """含图片关键词 → multimodal。"""
        resp = client.post("/api/v1/cost-router/classify", json={"text": "请描述这张图片"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "multimodal"

    def test_classify_moderate(self, client: TestClient) -> None:
        """中等长度无关键词 → moderate。"""
        text = "这是一个超过五十个字符的文本内容" * 5
        resp = client.post("/api/v1/cost-router/classify", json={"text": text})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "moderate"

    def test_classify_empty_text_rejected(self, client: TestClient) -> None:
        """空文本被 Pydantic 拒绝（min_length=1）。"""
        resp = client.post("/api/v1/cost-router/classify", json={"text": ""})
        assert resp.status_code == 422

    def test_classify_missing_text(self, client: TestClient) -> None:
        """缺少 text 字段 → 422。"""
        resp = client.post("/api/v1/cost-router/classify", json={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# /recommend 端点
# ═══════════════════════════════════════════════════════════════════


class TestRecommendEndpoint:
    """POST /api/v1/cost-router/recommend 端点测试。"""

    def test_recommend_with_match(self, client: TestClient) -> None:
        """DB 有匹配 Provider → 返回推荐。"""
        p = _make_provider_orm(name="gpt-4o", model_tier="moderate", capabilities=["text", "code"])
        session = _mock_db_session(p)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend",
                json={"text": "你好"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # 短文本 → simple tier，无 simple provider → 向上找到 moderate(gpt-4o)
            assert data["tier"] == "simple"
            assert data["provider_name"] == "gpt-4o"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_recommend_no_providers(self, client: TestClient) -> None:
        """DB 无 Provider → provider_name 为 null。"""
        session = _mock_db_session()
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend",
                json={"text": "你好"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["provider_name"] is None
            assert data["provider_tier"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_recommend_with_capability_filter(self, client: TestClient) -> None:
        """通过 capability 查询参数筛选。"""
        p_text = _make_provider_orm(name="gpt-mini", model_tier="simple", capabilities=["text"])
        p_vision = _make_provider_orm(name="gpt-4o-vision", model_tier="multimodal", capabilities=["text", "vision"])
        session = _mock_db_session(p_text, p_vision)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend?capability=vision",
                json={"text": "你好"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # 需要 vision 能力 → 只有 gpt-4o-vision 满足
            assert data["provider_name"] == "gpt-4o-vision"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_recommend_tier_upgrade(self, client: TestClient) -> None:
        """没有匹配 tier 时向上升级。"""
        # 只有 complex 级别的 Provider
        p = _make_provider_orm(name="claude-opus", model_tier="complex", capabilities=["text", "code"])
        session = _mock_db_session(p)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend",
                json={"text": "你好"},  # simple tier
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["tier"] == "simple"
            # 向上升级到 complex
            assert data["provider_name"] == "claude-opus"
            assert data["provider_tier"] == "complex"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_recommend_exact_tier_match(self, client: TestClient) -> None:
        """有精确 tier 匹配时优先选择同级。"""
        p_simple = _make_provider_orm(name="gpt-mini", model_tier="simple", capabilities=["text"])
        p_complex = _make_provider_orm(name="claude-opus", model_tier="complex", capabilities=["text"])
        session = _mock_db_session(p_simple, p_complex)
        app.dependency_overrides[get_db] = lambda: session
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend",
                json={"text": "你好"},  # simple tier
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["provider_name"] == "gpt-mini"
            assert data["provider_tier"] == "simple"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_recommend_empty_text_rejected(self, client: TestClient) -> None:
        """空文本被 422 拒绝。"""
        resp = client.post("/api/v1/cost-router/recommend", json={"text": ""})
        assert resp.status_code == 422
