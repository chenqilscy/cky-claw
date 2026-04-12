"""Intent 漂移检测 API 测试 — 关键词提取 / 漂移评分 / 阈值边界。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SVC = "app.api.intent"


class TestIntentDetection:
    """POST /api/v1/intent/detect 意图漂移检测。"""

    @patch(f"{SVC}._detector")
    def test_no_drift_same_topic(self, mock_detector: MagicMock) -> None:
        """相同主题的消息不应检测到漂移。"""
        signal = MagicMock()
        signal.original_keywords = frozenset(["agent", "配置"])
        signal.current_keywords = frozenset(["agent", "配置"])
        signal.drift_score = 0.0
        signal.is_drifted = False
        mock_detector.detect = AsyncMock(return_value=signal)

        resp = client.post(
            "/api/v1/intent/detect",
            json={
                "original_intent": "配置 Agent 参数",
                "current_message": "Agent 的配置选项",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_drifted"] is False
        assert body["drift_score"] == 0.0

    @patch(f"{SVC}._detector")
    def test_drift_different_topic(self, mock_detector: MagicMock) -> None:
        """话题发生显著偏移时应检测到漂移。"""
        signal = MagicMock()
        signal.original_keywords = frozenset(["agent", "配置"])
        signal.current_keywords = frozenset(["天气", "预报"])
        signal.drift_score = 1.0
        signal.is_drifted = True
        mock_detector.detect = AsyncMock(return_value=signal)

        resp = client.post(
            "/api/v1/intent/detect",
            json={
                "original_intent": "配置 Agent 参数",
                "current_message": "明天天气怎么样",
                "threshold": 0.6,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_drifted"] is True
        assert body["drift_score"] > 0.5

    @patch(f"{SVC}._detector")
    def test_threshold_boundary(self, mock_detector: MagicMock) -> None:
        """漂移评分恰好等于阈值时应标记为漂移。"""
        signal = MagicMock()
        signal.original_keywords = frozenset(["agent"])
        signal.current_keywords = frozenset(["tool"])
        signal.drift_score = 0.6
        signal.is_drifted = True
        mock_detector.detect = AsyncMock(return_value=signal)

        resp = client.post(
            "/api/v1/intent/detect",
            json={
                "original_intent": "Agent 管理",
                "current_message": "工具使用",
                "threshold": 0.6,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_drifted"] is True

    def test_missing_original_intent(self) -> None:
        """缺少 original_intent 应返回 422。"""
        resp = client.post(
            "/api/v1/intent/detect",
            json={"current_message": "测试"},
        )
        assert resp.status_code == 422

    def test_missing_current_message(self) -> None:
        """缺少 current_message 应返回 422。"""
        resp = client.post(
            "/api/v1/intent/detect",
            json={"original_intent": "测试"},
        )
        assert resp.status_code == 422

    def test_invalid_threshold_range(self) -> None:
        """threshold 超出 [0, 1] 范围应返回 422。"""
        resp = client.post(
            "/api/v1/intent/detect",
            json={
                "original_intent": "测试",
                "current_message": "测试",
                "threshold": 1.5,
            },
        )
        assert resp.status_code == 422

    @patch(f"{SVC}._detector")
    def test_response_contains_keywords(self, mock_detector: MagicMock) -> None:
        """响应中包含原始关键词和当前关键词。"""
        signal = MagicMock()
        signal.original_keywords = frozenset(["agent", "配置"])
        signal.current_keywords = frozenset(["agent", "模型"])
        signal.drift_score = 0.5
        signal.is_drifted = False
        mock_detector.detect = AsyncMock(return_value=signal)

        resp = client.post(
            "/api/v1/intent/detect",
            json={
                "original_intent": "配置 Agent",
                "current_message": "Agent 模型",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "original_keywords" in body
        assert "current_keywords" in body
        assert isinstance(body["original_keywords"], list)
