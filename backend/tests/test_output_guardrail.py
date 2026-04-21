"""Output Guardrail 端到端集成测试 — execute_run / execute_run_stream 的 TripwireError 处理。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ═══════════════════════════════════════════════════════════════════
# Mock 基础设施
# ═══════════════════════════════════════════════════════════════════


def _make_session_record(**overrides: Any) -> MagicMock:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_name": "test-agent",
        "status": "active",
        "title": "",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_agent_config(**overrides: Any) -> MagicMock:
    defaults = {
        "name": "test-agent",
        "description": "test",
        "instructions": "You are helpful",
        "model": "openai/test",
        "provider_name": None,
        "model_settings": None,
        "tool_groups": [],
        "handoffs": [],
        "guardrails": {"input": [], "output": [], "tool": []},
        "approval_mode": "full-auto",
        "mcp_servers": [],
        "agent_tools": [],
        "skills": [],
        "metadata_": {},
        "response_style": None,
        "is_active": True,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# execute_run — InputGuardrailTripwireError 处理
# ═══════════════════════════════════════════════════════════════════


class TestExecuteRunInputGuardrailBlocked:
    """execute_run 捕获 InputGuardrailTripwireError 返回 guardrail_blocked 状态。"""

    @pytest.mark.asyncio()
    async def test_input_guardrail_blocked_returns_response(self) -> None:
        from app.schemas.session import RunConfig, RunRequest
        from app.services.session import execute_run
        from kasaya.guardrails.result import InputGuardrailTripwireError

        sid = uuid.uuid4()
        session_mock = _make_session_record(id=sid)
        agent_mock = _make_agent_config()

        db = AsyncMock()
        # get_session → session_record
        # select AgentConfig → agent_config
        exec_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        db.execute = AsyncMock(side_effect=exec_results)
        db.commit = AsyncMock()

        request = RunRequest(input="hello", config=RunConfig(stream=False))

        with (
            patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_mock),
            patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_provider", new_callable=AsyncMock, return_value=({}, None)),
            patch("app.services.session._resolve_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_agent_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_tool_groups", new_callable=AsyncMock, return_value=[]),
            patch("kasaya.runner.runner.Runner.run", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.side_effect = InputGuardrailTripwireError(
                guardrail_name="block-injection", message="检测到注入攻击"
            )
            result = await execute_run(db, sid, request)

        assert result.status == "guardrail_blocked"
        assert "Input Guardrail" in result.output
        assert "block-injection" in result.output
        assert "检测到注入攻击" in result.output


# ═══════════════════════════════════════════════════════════════════
# execute_run — OutputGuardrailTripwireError 处理
# ═══════════════════════════════════════════════════════════════════


class TestExecuteRunOutputGuardrailBlocked:
    """execute_run 捕获 OutputGuardrailTripwireError 返回 guardrail_blocked 状态。"""

    @pytest.mark.asyncio()
    async def test_output_guardrail_blocked_returns_response(self) -> None:
        from app.schemas.session import RunConfig, RunRequest
        from app.services.session import execute_run
        from kasaya.guardrails.result import OutputGuardrailTripwireError

        sid = uuid.uuid4()
        session_mock = _make_session_record(id=sid)
        agent_mock = _make_agent_config()

        db = AsyncMock()
        exec_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        db.execute = AsyncMock(side_effect=exec_results)
        db.commit = AsyncMock()

        request = RunRequest(input="hello", config=RunConfig(stream=False))

        with (
            patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_mock),
            patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_provider", new_callable=AsyncMock, return_value=({}, None)),
            patch("app.services.session._resolve_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_agent_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_tool_groups", new_callable=AsyncMock, return_value=[]),
            patch("kasaya.runner.runner.Runner.run", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.side_effect = OutputGuardrailTripwireError(
                guardrail_name="pii-filter", message="检测到敏感信息输出"
            )
            result = await execute_run(db, sid, request)

        assert result.status == "guardrail_blocked"
        assert "Output Guardrail" in result.output
        assert "pii-filter" in result.output
        assert "检测到敏感信息输出" in result.output


# ═══════════════════════════════════════════════════════════════════
# execute_run_stream — Guardrail SSE 错误码
# ═══════════════════════════════════════════════════════════════════


class TestExecuteRunStreamGuardrailErrors:
    """execute_run_stream 对 Guardrail 异常使用特定 SSE 错误码。"""

    @pytest.mark.asyncio()
    async def test_input_guardrail_sse_error_code(self) -> None:
        import json

        from app.schemas.session import RunConfig, RunRequest
        from app.services.session import execute_run_stream
        from kasaya.guardrails.result import InputGuardrailTripwireError

        sid = uuid.uuid4()
        session_mock = _make_session_record(id=sid)
        agent_mock = _make_agent_config()

        db = AsyncMock()
        exec_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        db.execute = AsyncMock(side_effect=exec_results)
        db.commit = AsyncMock()

        request = RunRequest(input="hello", config=RunConfig(stream=True))

        async def mock_run_streamed_raise(**kwargs):  # type: ignore[no-untyped-def]
            raise InputGuardrailTripwireError(
                guardrail_name="block-injection", message="注入攻击"
            )
            yield  # Make it an async generator  # noqa: E501, RUF028

        with (
            patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_mock),
            patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_provider", new_callable=AsyncMock, return_value=({}, None)),
            patch("app.services.session._resolve_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_agent_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_tool_groups", new_callable=AsyncMock, return_value=[]),
            patch("kasaya.runner.runner.Runner.run_streamed") as mock_streamed,
        ):
            mock_streamed.side_effect = InputGuardrailTripwireError(
                guardrail_name="block-injection", message="注入攻击"
            )
            events = []
            async for sse in execute_run_stream(db, sid, request):
                events.append(sse)

        # 找到 error 事件
        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
        error_data = json.loads(error_events[0].split("data: ")[1].strip())
        assert error_data["code"] == "INPUT_GUARDRAIL_TRIGGERED"
        assert "Input Guardrail" in error_data["message"]

    @pytest.mark.asyncio()
    async def test_output_guardrail_sse_error_code(self) -> None:
        import json

        from app.schemas.session import RunConfig, RunRequest
        from app.services.session import execute_run_stream
        from kasaya.guardrails.result import OutputGuardrailTripwireError

        sid = uuid.uuid4()
        session_mock = _make_session_record(id=sid)
        agent_mock = _make_agent_config()

        db = AsyncMock()
        exec_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        db.execute = AsyncMock(side_effect=exec_results)
        db.commit = AsyncMock()

        request = RunRequest(input="hello", config=RunConfig(stream=True))

        with (
            patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_mock),
            patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_provider", new_callable=AsyncMock, return_value=({}, None)),
            patch("app.services.session._resolve_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_agent_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_tool_groups", new_callable=AsyncMock, return_value=[]),
            patch("kasaya.runner.runner.Runner.run_streamed") as mock_streamed,
        ):
            mock_streamed.side_effect = OutputGuardrailTripwireError(
                guardrail_name="pii-filter", message="敏感信息"
            )
            events = []
            async for sse in execute_run_stream(db, sid, request):
                events.append(sse)

        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
        error_data = json.loads(error_events[0].split("data: ")[1].strip())
        assert error_data["code"] == "OUTPUT_GUARDRAIL_TRIGGERED"
        assert "Output Guardrail" in error_data["message"]

    @pytest.mark.asyncio()
    async def test_generic_error_sse_code(self) -> None:
        import json

        from app.schemas.session import RunConfig, RunRequest
        from app.services.session import execute_run_stream

        sid = uuid.uuid4()
        session_mock = _make_session_record(id=sid)
        agent_mock = _make_agent_config()

        db = AsyncMock()
        exec_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        db.execute = AsyncMock(side_effect=exec_results)
        db.commit = AsyncMock()

        request = RunRequest(input="hello", config=RunConfig(stream=True))

        with (
            patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_mock),
            patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_provider", new_callable=AsyncMock, return_value=({}, None)),
            patch("app.services.session._resolve_mcp_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_agent_tools", new_callable=AsyncMock, return_value=[]),
            patch("app.services.session._resolve_tool_groups", new_callable=AsyncMock, return_value=[]),
            patch("kasaya.runner.runner.Runner.run_streamed") as mock_streamed,
        ):
            mock_streamed.side_effect = RuntimeError("LLM 调用失败")
            events = []
            async for sse in execute_run_stream(db, sid, request):
                events.append(sse)

        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
        error_data = json.loads(error_events[0].split("data: ")[1].strip())
        assert error_data["code"] == "RUN_FAILED"


# ═══════════════════════════════════════════════════════════════════
# _build_agent_from_config — LLM mode output guardrail
# ═══════════════════════════════════════════════════════════════════


class TestBuildAgentLLMOutputGuardrail:
    """_build_agent_from_config 处理 LLM mode output guardrail。"""

    def test_llm_output_guardrail_injected(self) -> None:
        from app.services.session import _build_agent_from_config

        agent_config = _make_agent_config()
        rule = MagicMock()
        rule.name = "llm-out"
        rule.type = "output"
        rule.mode = "llm"
        rule.config = {"preset": "content_safety", "model": "gpt-4o-mini", "threshold": 0.8}

        agent = _build_agent_from_config(agent_config, guardrail_rules=[rule])
        assert len(agent.output_guardrails) == 1
        assert agent.output_guardrails[0].name == "llm-out"
        assert len(agent.input_guardrails) == 0

    def test_llm_tool_guardrail_injected(self) -> None:
        from app.services.session import _build_agent_from_config

        agent_config = _make_agent_config()
        rule = MagicMock()
        rule.name = "llm-tool"
        rule.type = "tool"
        rule.mode = "llm"
        rule.config = {"preset": "prompt_injection", "model": "gpt-4o-mini", "threshold": 0.7}

        agent = _build_agent_from_config(agent_config, guardrail_rules=[rule])
        assert len(agent.tool_guardrails) == 1
        assert agent.tool_guardrails[0].name == "llm-tool"
        assert len(agent.input_guardrails) == 0
        assert len(agent.output_guardrails) == 0


# ═══════════════════════════════════════════════════════════════════
# RunResponse status 字段
# ═══════════════════════════════════════════════════════════════════


class TestRunResponseGuardrailStatus:
    """RunResponse schema 接受 guardrail_blocked 状态。"""

    def test_guardrail_blocked_status(self) -> None:
        from app.schemas.session import RunResponse, TokenUsageResponse

        resp = RunResponse(
            run_id="r-1",
            status="guardrail_blocked",
            output="[Output Guardrail] pii-filter: 敏感信息",
            token_usage=TokenUsageResponse(),
            duration_ms=50,
            turn_count=0,
            last_agent_name="test-agent",
        )
        assert resp.status == "guardrail_blocked"
        assert "Output Guardrail" in resp.output
