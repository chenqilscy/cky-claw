"""LLM-as-Judge 自动评估服务测试。

覆盖：
- _parse_judge_response: 各种 LLM 输出格式解析
- _build_judge_prompt: prompt 构建
- auto_evaluate_run: 完整评估流程（mock LLM）
- auto_evaluate_by_run_id: 从 Trace 提取上下文
- API 端点: POST /auto 和 POST /auto/{run_id}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db as get_db_dep
from app.core.deps import require_admin
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _orm(**fields: object) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _override_admin() -> None:
    app.dependency_overrides[require_admin] = lambda: {"user_id": str(uuid.uuid4()), "role": "admin"}


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    db_mock = AsyncMock()
    app.dependency_overrides[get_db_dep] = lambda: db_mock
    return TestClient(app)


# ---------------------------------------------------------------------------
# _parse_judge_response 单元测试
# ---------------------------------------------------------------------------


class TestParseJudgeResponse:
    """解析 LLM Judge 回复的各种格式。"""

    def test_parse_plain_json(self) -> None:
        """纯 JSON 格式。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = json.dumps({
            "accuracy": 0.8, "relevance": 0.9, "coherence": 0.7,
            "helpfulness": 0.6, "safety": 1.0, "efficiency": 0.5,
            "tool_usage": 0.8, "comment": "不错",
        })
        result = _parse_judge_response(text)
        assert result["accuracy"] == 0.8
        assert result["relevance"] == 0.9
        assert result["safety"] == 1.0
        assert result["comment"] == "不错"

    def test_parse_markdown_code_block(self) -> None:
        """Markdown ```json 代码块。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = """```json
{
  "accuracy": 0.7,
  "relevance": 0.8,
  "coherence": 0.6,
  "helpfulness": 0.9,
  "safety": 1.0,
  "efficiency": 0.5,
  "tool_usage": 0.7,
  "comment": "回复质量中等"
}
```"""
        result = _parse_judge_response(text)
        assert result["accuracy"] == 0.7
        assert result["helpfulness"] == 0.9
        assert result["comment"] == "回复质量中等"

    def test_parse_json_embedded_in_text(self) -> None:
        """JSON 嵌入在前后文本中。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = 'Here is the evaluation: {"accuracy": 0.5, "relevance": 0.6, "coherence": 0.7, "helpfulness": 0.8, "safety": 0.9, "efficiency": 0.4, "tool_usage": 0.3, "comment": "ok"} Done.'
        result = _parse_judge_response(text)
        assert result["accuracy"] == 0.5
        assert result["efficiency"] == 0.4

    def test_clamp_out_of_range(self) -> None:
        """超出范围的值应被钳位到 [0.0, 1.0]。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = json.dumps({
            "accuracy": 1.5, "relevance": -0.3, "coherence": 0.5,
            "helpfulness": 0.5, "safety": 0.5, "efficiency": 0.5,
            "tool_usage": 0.5, "comment": "ok",
        })
        result = _parse_judge_response(text)
        assert result["accuracy"] == 1.0
        assert result["relevance"] == 0.0

    def test_missing_dimensions_default_to_0_5(self) -> None:
        """缺失维度应默认为 0.5。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = json.dumps({"accuracy": 0.9, "comment": "partial"})
        result = _parse_judge_response(text)
        assert result["accuracy"] == 0.9
        assert result["relevance"] == 0.5  # default
        assert result["comment"] == "partial"

    def test_invalid_json_raises(self) -> None:
        """完全无效的文本应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.auto_evaluator import _parse_judge_response

        with pytest.raises(ValidationError):
            _parse_judge_response("This is not JSON at all.")

    def test_long_comment_truncated(self) -> None:
        """超长评语应被截断到 500 字符。"""
        from app.services.auto_evaluator import _parse_judge_response

        text = json.dumps({
            "accuracy": 0.8, "relevance": 0.8, "coherence": 0.8,
            "helpfulness": 0.8, "safety": 0.8, "efficiency": 0.8,
            "tool_usage": 0.8, "comment": "x" * 1000,
        })
        result = _parse_judge_response(text)
        assert len(result["comment"]) == 500


# ---------------------------------------------------------------------------
# _build_judge_prompt 单元测试
# ---------------------------------------------------------------------------


class TestBuildJudgePrompt:
    """评估 prompt 构建。"""

    def test_basic_prompt(self) -> None:
        from app.services.auto_evaluator import _build_judge_prompt

        prompt = _build_judge_prompt(
            user_input="你好",
            agent_output="你好！有什么可以帮你的？",
            duration_ms=500,
            total_tokens=100,
        )
        assert "你好" in prompt
        assert "500ms" in prompt
        assert "100" in prompt

    def test_truncation(self) -> None:
        """超长输入应被截断。"""
        from app.services.auto_evaluator import _build_judge_prompt

        prompt = _build_judge_prompt(
            user_input="a" * 5000,
            agent_output="b" * 10000,
        )
        # user_input 截断到 2000，agent_output 截断到 4000
        assert len(prompt) < 10000

    def test_trace_summary_included(self) -> None:
        from app.services.auto_evaluator import _build_judge_prompt

        prompt = _build_judge_prompt(
            user_input="test",
            agent_output="result",
            trace_summary="工具调用: web_search | Span 数量: 5",
        )
        assert "web_search" in prompt


# ---------------------------------------------------------------------------
# auto_evaluate_run（mock LLM）
# ---------------------------------------------------------------------------


class TestAutoEvaluateRun:
    """完整的 LLM 自动评估流程。"""

    @pytest.mark.asyncio
    async def test_successful_evaluation(self) -> None:
        """成功调用 LLM Judge 并创建评估记录。"""
        from app.services.auto_evaluator import auto_evaluate_run

        judge_response = json.dumps({
            "accuracy": 0.8, "relevance": 0.9, "coherence": 0.7,
            "helpfulness": 0.85, "safety": 1.0, "efficiency": 0.6,
            "tool_usage": 0.8, "comment": "回复准确且相关",
        })

        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = judge_response

        mock_eval = _orm(
            id=uuid.uuid4(), run_id="run-123", agent_id=None,
            accuracy=0.8, relevance=0.9, coherence=0.7,
            helpfulness=0.85, safety=1.0, efficiency=0.6,
            tool_usage=0.8, overall_score=0.82,
            eval_method="llm_judge", evaluator="deepseek/deepseek-chat",
            comment="回复准确且相关", created_at=_now(),
        )

        db = AsyncMock()
        with (
            patch("app.services.auto_evaluator.litellm") as mock_litellm,
            patch("app.services.auto_evaluator.create_evaluation", new_callable=AsyncMock, return_value=mock_eval) as mock_create,
        ):
            mock_litellm.acompletion = AsyncMock(return_value=mock_llm_response)
            result = await auto_evaluate_run(
                db,
                run_id="run-123",
                user_input="什么是机器学习？",
                agent_output="机器学习是人工智能的一个分支...",
                duration_ms=1000,
                total_tokens=500,
            )

        assert result.eval_method == "llm_judge"
        assert mock_create.called
        call_data = mock_create.call_args[0][1]
        assert call_data.accuracy == 0.8
        assert call_data.eval_method == "llm_judge"

    @pytest.mark.asyncio
    async def test_llm_call_failure(self) -> None:
        """LLM 调用失败应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.auto_evaluator import auto_evaluate_run

        db = AsyncMock()
        with patch("app.services.auto_evaluator.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=Exception("API Error"))
            with pytest.raises(ValidationError, match="LLM Judge 调用失败"):
                await auto_evaluate_run(
                    db,
                    run_id="run-fail",
                    user_input="test",
                    agent_output="test",
                )

    @pytest.mark.asyncio
    async def test_invalid_llm_response(self) -> None:
        """LLM 返回无效 JSON 应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.auto_evaluator import auto_evaluate_run

        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "I cannot evaluate this."

        db = AsyncMock()
        with patch("app.services.auto_evaluator.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_llm_response)
            with pytest.raises(ValidationError, match="无法解析"):
                await auto_evaluate_run(
                    db,
                    run_id="run-bad",
                    user_input="test",
                    agent_output="test",
                )

    @pytest.mark.asyncio
    async def test_custom_judge_model(self) -> None:
        """可以指定自定义 Judge 模型。"""
        from app.services.auto_evaluator import auto_evaluate_run

        judge_response = json.dumps({
            "accuracy": 0.5, "relevance": 0.5, "coherence": 0.5,
            "helpfulness": 0.5, "safety": 0.5, "efficiency": 0.5,
            "tool_usage": 0.5, "comment": "average",
        })

        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = judge_response

        mock_eval = _orm(
            id=uuid.uuid4(), run_id="run-custom", agent_id=None,
            accuracy=0.5, relevance=0.5, coherence=0.5,
            helpfulness=0.5, safety=0.5, efficiency=0.5,
            tool_usage=0.5, overall_score=0.5,
            eval_method="llm_judge", evaluator="openai/gpt-4",
            comment="average", created_at=_now(),
        )

        db = AsyncMock()
        with (
            patch("app.services.auto_evaluator.litellm") as mock_litellm,
            patch("app.services.auto_evaluator.create_evaluation", new_callable=AsyncMock, return_value=mock_eval),
        ):
            mock_litellm.acompletion = AsyncMock(return_value=mock_llm_response)
            result = await auto_evaluate_run(
                db,
                run_id="run-custom",
                user_input="test",
                agent_output="test",
                judge_model="openai/gpt-4",
            )

        # 验证 litellm 使用了指定模型
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-4"


# ---------------------------------------------------------------------------
# API 端点测试
# ---------------------------------------------------------------------------


class TestAutoEvaluateAPI:
    """自动评估 API 端点。"""

    def test_auto_evaluate_with_context(self, client: TestClient) -> None:
        """POST /auto — 提供上下文的自动评估。"""
        _override_admin()
        mock_eval = _orm(
            id=uuid.uuid4(), run_id="run-api", agent_id=None,
            accuracy=0.8, relevance=0.8, coherence=0.8,
            helpfulness=0.8, safety=1.0, efficiency=0.7,
            tool_usage=0.8, overall_score=0.82,
            eval_method="llm_judge", evaluator="deepseek/deepseek-chat",
            comment="good", created_at=_now(),
        )
        with patch(
            "app.services.auto_evaluator._resolve_judge_provider",
            new_callable=AsyncMock,
            return_value={"api_key": "sk-test"},
        ), patch(
            "app.services.auto_evaluator.auto_evaluate_run",
            new_callable=AsyncMock,
            return_value=mock_eval,
        ):
            resp = client.post("/api/v1/evaluations/auto", json={
                "run_id": "run-api",
                "user_input": "你好",
                "agent_output": "你好！有什么可以帮你的？",
                "duration_ms": 500,
                "total_tokens": 100,
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["eval_method"] == "llm_judge"
        assert data["accuracy"] == 0.8

    def test_auto_evaluate_validation_error(self, client: TestClient) -> None:
        """POST /auto — LLM 调用失败返回 422。"""
        from app.core.exceptions import ValidationError

        _override_admin()
        with patch(
            "app.services.auto_evaluator._resolve_judge_provider",
            new_callable=AsyncMock,
            return_value={"api_key": "sk-test"},
        ), patch(
            "app.services.auto_evaluator.auto_evaluate_run",
            new_callable=AsyncMock,
            side_effect=ValidationError("LLM Judge 调用失败: timeout"),
        ):
            resp = client.post("/api/v1/evaluations/auto", json={
                "run_id": "run-fail",
                "user_input": "test",
                "agent_output": "test",
            })
        assert resp.status_code == 422

    def test_auto_evaluate_by_run_id(self, client: TestClient) -> None:
        """POST /auto/{run_id} — 从 Trace 自动评估。"""
        _override_admin()
        mock_eval = _orm(
            id=uuid.uuid4(), run_id="run-trace", agent_id=None,
            accuracy=0.7, relevance=0.7, coherence=0.7,
            helpfulness=0.7, safety=1.0, efficiency=0.6,
            tool_usage=0.5, overall_score=0.71,
            eval_method="llm_judge", evaluator="deepseek/deepseek-chat",
            comment="ok", created_at=_now(),
        )
        with patch(
            "app.services.auto_evaluator.auto_evaluate_by_run_id",
            new_callable=AsyncMock,
            return_value=mock_eval,
        ):
            resp = client.post("/api/v1/evaluations/auto/run-trace")
        assert resp.status_code == 201
        assert resp.json()["run_id"] == "run-trace"

    def test_auto_evaluate_by_run_id_not_found(self, client: TestClient) -> None:
        """POST /auto/{run_id} — Trace 不存在返回 404。"""
        from app.core.exceptions import NotFoundError

        _override_admin()
        with patch(
            "app.services.auto_evaluator.auto_evaluate_by_run_id",
            new_callable=AsyncMock,
            side_effect=NotFoundError("找不到 run_id"),
        ):
            resp = client.post(f"/api/v1/evaluations/auto/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_auto_evaluate_missing_fields(self, client: TestClient) -> None:
        """POST /auto — 缺少必填字段返回 422。"""
        _override_admin()
        resp = client.post("/api/v1/evaluations/auto", json={
            "run_id": "run-missing",
            # 缺少 user_input 和 agent_output
        })
        assert resp.status_code == 422

    def test_auto_evaluate_requires_admin(self, client: TestClient) -> None:
        """非 admin 用户请求自动评估端点应返回 403。"""
        # 覆盖为非 admin 用户
        non_admin = MagicMock()
        non_admin.id = uuid.uuid4()
        non_admin.username = "user"
        non_admin.role = "user"
        non_admin.role_id = None
        non_admin.org_id = None
        non_admin.is_active = True
        from app.core.deps import get_current_user
        app.dependency_overrides[get_current_user] = lambda: non_admin
        resp = client.post("/api/v1/evaluations/auto", json={
            "run_id": "run-noauth",
            "user_input": "test",
            "agent_output": "test",
        })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TraceProcessor run_id 存储测试
# ---------------------------------------------------------------------------


class TestTraceProcessorRunId:
    """验证 PostgresTraceProcessor 正确存储 run_id 到 metadata。"""

    @pytest.mark.asyncio
    async def test_run_id_stored_in_metadata(self) -> None:
        """on_trace_end 应将 run_id 写入 metadata。"""
        from app.services.trace_processor import PostgresTraceProcessor

        processor = PostgresTraceProcessor(session_id="sess-1", run_id="run-abc")

        # Mock trace
        trace = MagicMock()
        trace.trace_id = "trace-1"
        trace.workflow_name = "test"
        trace.group_id = None
        trace.start_time = _now()
        trace.end_time = _now()
        trace.spans = []

        await processor.on_trace_start(trace)
        await processor.on_trace_end(trace)

        data, _ = processor.get_collected_data()
        assert data is not None
        assert data["metadata_"]["run_id"] == "run-abc"

    @pytest.mark.asyncio
    async def test_no_run_id_no_metadata(self) -> None:
        """不传 run_id 时，metadata 不包含 run_id。"""
        from app.services.trace_processor import PostgresTraceProcessor

        processor = PostgresTraceProcessor(session_id="sess-1")

        trace = MagicMock()
        trace.trace_id = "trace-2"
        trace.workflow_name = "test"
        trace.group_id = None
        trace.start_time = _now()
        trace.end_time = _now()
        trace.spans = []

        await processor.on_trace_start(trace)
        await processor.on_trace_end(trace)

        data, _ = processor.get_collected_data()
        assert data is not None
        assert "run_id" not in data.get("metadata_", {})
