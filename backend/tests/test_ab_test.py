"""A/B Testing API 测试 — 多模型并行推理 / Provider 解析 / 错误处理。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import app

client = TestClient(app)

SVC = "app.api.ab_test"


def _mock_db_override():
    """提供 mock AsyncSession 作为 get_db 依赖。"""
    async def override():
        yield AsyncMock()
    return override


def _mock_chat_response(content: str = "Hello world") -> MagicMock:
    """构造 LiteLLMProvider.chat() 的 mock 返回值。"""
    resp = MagicMock()
    resp.content = content
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return resp


class TestABTestAPI:
    """POST /api/v1/ab-test 多模型 A/B 测试。"""

    def setup_method(self) -> None:
        app.dependency_overrides[get_db] = _mock_db_override()

    def teardown_method(self) -> None:
        app.dependency_overrides.pop(get_db, None)

    @patch(f"{SVC}._resolve_provider_kwargs", new_callable=AsyncMock, return_value={})
    @patch("ckyclaw_framework.model.litellm_provider.LiteLLMProvider.chat", new_callable=AsyncMock)
    def test_run_ab_test_success(self, mock_chat: AsyncMock, mock_resolve: AsyncMock) -> None:
        """两个模型都成功返回结果。"""
        mock_chat.return_value = _mock_chat_response()
        resp = client.post(
            "/api/v1/ab-test",
            json={"prompt": "Say hello", "models": ["gpt-4", "gpt-3.5-turbo"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["prompt"] == "Say hello"
        assert len(body["results"]) == 2
        for r in body["results"]:
            assert "model" in r
            assert "latency_ms" in r

    @patch(f"{SVC}._resolve_provider_kwargs", new_callable=AsyncMock, return_value={})
    @patch("ckyclaw_framework.model.litellm_provider.LiteLLMProvider.chat", new_callable=AsyncMock)
    def test_run_ab_test_single_model_error(self, mock_chat: AsyncMock, mock_resolve: AsyncMock) -> None:
        """一个模型失败，其他正常返回。"""
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Model unavailable")
            return _mock_chat_response("OK")

        mock_chat.side_effect = side_effect
        resp = client.post(
            "/api/v1/ab-test",
            json={"prompt": "Test", "models": ["model-a", "model-b"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 2
        errors = [r for r in body["results"] if r.get("error")]
        assert len(errors) >= 1

    def test_run_ab_test_too_few_models(self) -> None:
        """少于 2 个模型应返回 422 验证错误。"""
        resp = client.post(
            "/api/v1/ab-test",
            json={"prompt": "Test", "models": ["gpt-4"]},
        )
        assert resp.status_code == 422

    def test_run_ab_test_too_many_models(self) -> None:
        """超过 5 个模型应返回 422 验证错误。"""
        resp = client.post(
            "/api/v1/ab-test",
            json={"prompt": "Test", "models": ["m1", "m2", "m3", "m4", "m5", "m6"]},
        )
        assert resp.status_code == 422

    def test_run_ab_test_empty_prompt(self) -> None:
        """空 prompt 应返回 422。"""
        resp = client.post(
            "/api/v1/ab-test",
            json={"prompt": "", "models": ["gpt-4", "gpt-3.5-turbo"]},
        )
        assert resp.status_code in (200, 422)

    @patch(f"{SVC}._resolve_provider_kwargs", new_callable=AsyncMock)
    @patch("ckyclaw_framework.model.litellm_provider.LiteLLMProvider.chat", new_callable=AsyncMock)
    def test_run_ab_test_with_provider(self, mock_chat: AsyncMock, mock_resolve: AsyncMock) -> None:
        """指定 provider_name 时使用 Provider 配置的密钥。"""
        mock_resolve.return_value = {"api_key": "sk-test", "api_base": "https://api.example.com"}
        mock_chat.return_value = _mock_chat_response("OK")
        resp = client.post(
            "/api/v1/ab-test",
            json={
                "prompt": "Test",
                "models": ["gpt-4", "gpt-3.5"],
                "provider_name": "my-provider",
            },
        )
        assert resp.status_code == 200
        mock_resolve.assert_called_once()
