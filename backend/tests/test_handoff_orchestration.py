"""Multi-Agent Handoff 编排单元测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.session import (
    _MAX_HANDOFF_DEPTH,
    _build_agent_from_config,
    _resolve_handoff_agents,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """创建 AgentConfig Mock 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-agent",
        "description": "测试 Agent",
        "instructions": "你是一个测试助手",
        "model": "gpt-4o-mini",
        "model_settings": None,
        "tool_groups": [],
        "handoffs": [],
        "guardrails": {},
        "approval_mode": "suggest",
        "mcp_servers": [],
        "agent_tools": [],
        "provider_name": None,
        "skills": [],
        "metadata_": {},
        "response_style": None,
        "org_id": None,
        "is_active": True,
        "created_by": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# _build_agent_from_config + handoffs 参数测试
# ---------------------------------------------------------------------------


class TestBuildAgentWithHandoffs:
    """测试 _build_agent_from_config 正确处理 handoff_agents 参数。"""

    def test_without_handoffs(self) -> None:
        config = _make_agent_config(name="triage")
        agent = _build_agent_from_config(config)
        assert agent.name == "triage"
        assert agent.handoffs == []

    def test_with_empty_handoffs(self) -> None:
        config = _make_agent_config(name="triage")
        agent = _build_agent_from_config(config, handoff_agents=[])
        assert agent.handoffs == []

    def test_with_handoff_agents(self) -> None:
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.handoff.handoff import Handoff

        specialist = Agent(name="specialist", description="专家")
        handoff = Handoff(agent=specialist)

        config = _make_agent_config(name="triage")
        agent = _build_agent_from_config(config, handoff_agents=[handoff])

        assert len(agent.handoffs) == 1
        assert isinstance(agent.handoffs[0], Handoff)
        assert agent.handoffs[0].agent.name == "specialist"

    def test_with_multiple_handoffs(self) -> None:
        from ckyclaw_framework.agent.agent import Agent
        from ckyclaw_framework.handoff.handoff import Handoff

        spec1 = Agent(name="specialist-a", description="A")
        spec2 = Agent(name="specialist-b", description="B")

        config = _make_agent_config(name="triage")
        agent = _build_agent_from_config(
            config,
            handoff_agents=[Handoff(agent=spec1), Handoff(agent=spec2)],
        )

        assert len(agent.handoffs) == 2
        names = {h.agent.name for h in agent.handoffs}
        assert names == {"specialist-a", "specialist-b"}


# ---------------------------------------------------------------------------
# _resolve_handoff_agents 测试
# ---------------------------------------------------------------------------


def _mock_db_execute_for_configs(configs_by_name: dict[str, MagicMock]):
    """创建 mock DB，根据查询的 agent 名称返回对应 config。"""

    async def mock_execute(stmt):
        # 提取 WHERE 子句中的 name 列表
        # 简单实现：从 stmt 中提取 IN 子句的值
        result_mock = MagicMock()
        scalars_mock = MagicMock()

        # 提取查询的名称（测试中直接传入）
        found = []
        for _name, config in configs_by_name.items():
            found.append(config)
        scalars_mock.all.return_value = found
        result_mock.scalars.return_value = scalars_mock
        return result_mock

    return mock_execute


class TestResolveHandoffAgents:
    """测试 _resolve_handoff_agents 递归解析。"""

    @pytest.mark.asyncio
    async def test_no_handoffs(self) -> None:
        """无 handoffs 时返回空列表。"""
        config = _make_agent_config(name="solo-agent", handoffs=[])
        db = AsyncMock()

        result = await _resolve_handoff_agents(db, config)

        assert result == []
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_handoff(self) -> None:
        """单个 handoff 目标正常解析。"""
        main_config = _make_agent_config(name="triage", handoffs=["specialist"])
        target_config = _make_agent_config(name="specialist", handoffs=[], description="处理专业问题")

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [target_config]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        db.execute.return_value = execute_result

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, main_config)

        assert len(result) == 1
        assert result[0].agent.name == "specialist"
        assert result[0].agent.description == "处理专业问题"

    @pytest.mark.asyncio
    async def test_multiple_handoffs(self) -> None:
        """多个 handoff 目标正常解析。"""
        main_config = _make_agent_config(name="triage", handoffs=["analyst", "coder"])
        analyst_config = _make_agent_config(name="analyst", handoffs=[])
        coder_config = _make_agent_config(name="coder", handoffs=[])

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [analyst_config, coder_config]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        db.execute.return_value = execute_result

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, main_config)

        assert len(result) == 2
        names = {h.agent.name for h in result}
        assert names == {"analyst", "coder"}

    @pytest.mark.asyncio
    async def test_missing_target_skipped(self) -> None:
        """缺失的 handoff 目标被安全跳过。"""
        main_config = _make_agent_config(name="triage", handoffs=["existing", "missing"])
        existing_config = _make_agent_config(name="existing", handoffs=[])

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [existing_config]  # missing 不在结果中
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        db.execute.return_value = execute_result

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, main_config)

        assert len(result) == 1
        assert result[0].agent.name == "existing"

    @pytest.mark.asyncio
    async def test_circular_reference_detected(self) -> None:
        """循环引用被检测并安全跳过。"""
        # A → B → A（循环）
        config_a = _make_agent_config(name="agent-a", handoffs=["agent-b"])
        config_b = _make_agent_config(name="agent-b", handoffs=["agent-a"])

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            scalars_mock = MagicMock()
            if call_count == 1:
                scalars_mock.all.return_value = [config_b]
            else:
                # agent-a 在 visited 中，所以此次查询不应该查 agent-a
                scalars_mock.all.return_value = []
            result_mock.scalars.return_value = scalars_mock
            return result_mock

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, config_a)

        # A → B 被正常解析，B → A 被循环检测跳过
        assert len(result) == 1
        assert result[0].agent.name == "agent-b"
        # B 的 handoffs 应为空（A 被跳过）
        assert result[0].agent.handoffs == []

    @pytest.mark.asyncio
    async def test_recursive_handoffs(self) -> None:
        """多级 handoff 链正常递归解析。"""
        # triage → specialist → sub-specialist
        triage_config = _make_agent_config(name="triage", handoffs=["specialist"])
        specialist_config = _make_agent_config(name="specialist", handoffs=["sub-specialist"])
        sub_specialist_config = _make_agent_config(name="sub-specialist", handoffs=[])

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            scalars_mock = MagicMock()
            if call_count == 1:
                scalars_mock.all.return_value = [specialist_config]
            elif call_count == 2:
                scalars_mock.all.return_value = [sub_specialist_config]
            else:
                scalars_mock.all.return_value = []
            result_mock.scalars.return_value = scalars_mock
            return result_mock

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, triage_config)

        assert len(result) == 1
        specialist_handoff = result[0]
        assert specialist_handoff.agent.name == "specialist"
        # specialist 应有 sub-specialist 作为 handoff
        assert len(specialist_handoff.agent.handoffs) == 1
        assert specialist_handoff.agent.handoffs[0].agent.name == "sub-specialist"

    @pytest.mark.asyncio
    async def test_depth_limit(self) -> None:
        """递归深度超过 _MAX_HANDOFF_DEPTH 时被截断。"""
        # 创建一个超长链
        configs = {}
        for i in range(_MAX_HANDOFF_DEPTH + 2):
            name = f"agent-{i}"
            next_name = f"agent-{i + 1}" if i < _MAX_HANDOFF_DEPTH + 1 else ""
            handoffs = [next_name] if next_name else []
            configs[name] = _make_agent_config(name=name, handoffs=handoffs)

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            scalars_mock = MagicMock()
            # 返回下一级的 config
            target_name = f"agent-{call_count}"
            if target_name in configs:
                scalars_mock.all.return_value = [configs[target_name]]
            else:
                scalars_mock.all.return_value = []
            result_mock.scalars.return_value = scalars_mock
            return result_mock

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, configs["agent-0"])

        # 应该有 agent-1 在 handoffs 中
        assert len(result) == 1
        # 验证链不会超过 MAX_HANDOFF_DEPTH
        depth = 0
        current = result[0].agent
        while current.handoffs:
            depth += 1
            current = current.handoffs[0].agent
        assert depth < _MAX_HANDOFF_DEPTH

    @pytest.mark.asyncio
    async def test_handoff_with_guardrails(self) -> None:
        """目标 Agent 的 guardrails 被正确加载。"""
        main_config = _make_agent_config(
            name="triage",
            handoffs=["specialist"],
        )
        specialist_config = _make_agent_config(
            name="specialist",
            handoffs=[],
            guardrails={"input": ["block-pii"]},
        )

        # Mock guardrail rule
        mock_rule = MagicMock()
        mock_rule.type = "input"
        mock_rule.mode = "regex"
        mock_rule.name = "block-pii"
        mock_rule.config = {"patterns": [r"\d{3}-\d{2}-\d{4}"], "message": "PII detected"}

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [specialist_config]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        db.execute.return_value = execute_result

        with patch(
            "app.services.guardrail.get_guardrail_rules_by_names",
            new_callable=AsyncMock,
            return_value=[mock_rule],
        ):
            result = await _resolve_handoff_agents(db, main_config)

        assert len(result) == 1
        specialist_agent = result[0].agent
        assert specialist_agent.name == "specialist"
        # 验证 guardrails 被加载
        assert len(specialist_agent.input_guardrails) == 1
        assert specialist_agent.input_guardrails[0].name == "block-pii"

    @pytest.mark.asyncio
    async def test_self_reference_skipped(self) -> None:
        """Agent 自引用自己作为 handoff 目标被跳过。"""
        config = _make_agent_config(name="self-ref", handoffs=["self-ref"])
        db = AsyncMock()

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_handoff_agents(db, config)

        assert result == []


# ---------------------------------------------------------------------------
# _MAX_HANDOFF_DEPTH 常量验证
# ---------------------------------------------------------------------------


class TestHandoffConstants:
    def test_max_depth_is_positive(self) -> None:
        assert _MAX_HANDOFF_DEPTH > 0

    def test_max_depth_is_reasonable(self) -> None:
        assert _MAX_HANDOFF_DEPTH <= 10


# ---------------------------------------------------------------------------
# Handoff 工具名称生成验证（Framework 层集成）
# ---------------------------------------------------------------------------


class TestHandoffToolIntegration:
    """验证从 DB 构建的 Handoff 在 Framework Runner 中能正确生成工具。"""

    def test_handoff_generates_transfer_tool(self) -> None:
        """Handoff 对象能被 _build_tool_schemas 正确处理。"""
        from ckyclaw_framework.runner.runner import _build_tool_schemas

        config_triage = _make_agent_config(name="triage")
        config_specialist = _make_agent_config(name="specialist", description="处理专业问题")

        specialist_agent = _build_agent_from_config(config_specialist)
        from ckyclaw_framework.handoff.handoff import Handoff

        triage_agent = _build_agent_from_config(
            config_triage,
            handoff_agents=[Handoff(agent=specialist_agent)],
        )

        schemas = _build_tool_schemas(triage_agent)

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "transfer_to_specialist"
        assert "处理专业问题" in schemas[0]["function"]["description"]

    def test_multiple_handoffs_generate_tools(self) -> None:
        """多个 Handoff 目标生成多个 transfer 工具。"""
        from ckyclaw_framework.handoff.handoff import Handoff
        from ckyclaw_framework.runner.runner import _build_tool_schemas

        agent_a = _build_agent_from_config(_make_agent_config(name="agent-a", description="A"))
        agent_b = _build_agent_from_config(_make_agent_config(name="agent-b", description="B"))

        triage = _build_agent_from_config(
            _make_agent_config(name="triage"),
            handoff_agents=[Handoff(agent=agent_a), Handoff(agent=agent_b)],
        )

        schemas = _build_tool_schemas(triage)

        assert len(schemas) == 2
        tool_names = {s["function"]["name"] for s in schemas}
        assert tool_names == {"transfer_to_agent-a", "transfer_to_agent-b"}


# ---------------------------------------------------------------------------
# execute_run 中 Handoff 集成测试
# ---------------------------------------------------------------------------


class TestExecuteRunHandoffIntegration:
    """验证 execute_run 和 execute_run_stream 正确调用 _resolve_handoff_agents。"""

    @pytest.mark.asyncio
    @patch("app.services.session._resolve_handoff_agents", new_callable=AsyncMock, return_value=[])
    @patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[])
    @patch("app.services.session._save_trace_from_processor")
    @patch("app.services.session._save_token_usage_from_trace")
    async def test_execute_run_calls_resolve_handoffs(
        self,
        mock_save_token: AsyncMock,
        mock_save_trace: AsyncMock,
        mock_guardrails: AsyncMock,
        mock_resolve: AsyncMock,
    ) -> None:
        """execute_run 调用 _resolve_handoff_agents。"""
        from app.schemas.session import RunConfig, RunRequest

        mock_db = AsyncMock()
        session_record = MagicMock()
        session_record.agent_name = "triage"
        session_record.updated_at = datetime.now(UTC)

        agent_config = _make_agent_config(name="triage", handoffs=["specialist"])

        # Mock get_session
        with patch("app.services.session.get_session", new_callable=AsyncMock, return_value=session_record):
            # Mock DB execute for agent config
            scalars_mock = MagicMock()
            scalars_mock.scalar_one_or_none.return_value = agent_config
            mock_db.execute.return_value = scalars_mock

            # Mock Runner.run (imported inside function)
            mock_result = MagicMock()
            mock_result.output = "test output"
            mock_result.token_usage = None
            mock_result.turn_count = 1
            mock_result.last_agent_name = "triage"
            mock_result.trace = None
            with patch("ckyclaw_framework.runner.runner.Runner.run", new_callable=AsyncMock, return_value=mock_result):
                from app.services.session import execute_run

                request = RunRequest(input="hello", config=RunConfig(stream=False))
                result = await execute_run(mock_db, uuid.uuid4(), request)

                # 验证 _resolve_handoff_agents 被调用
                mock_resolve.assert_awaited_once()
                assert result.output == "test output"
