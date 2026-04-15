"""Phase 6.9 后端端到端集成测试 — 完整链路验证。

验证 _build_agent_from_config + _resolve_* 系列函数 + execute_run 的综合协作。
使用 MagicMock 模拟 DB 层，但实际执行 Framework Runner。
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# _build_agent_from_config 综合测试
# ---------------------------------------------------------------------------


class TestBuildAgentCombined:
    """验证 _build_agent_from_config 在各种配置组合下构建正确的 Agent。"""

    def test_all_tools_combined(self) -> None:
        """MCP 工具 + Agent-as-Tool + ToolGroup 工具全部合并到 Agent。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "full-agent"
        config.description = "Full featured agent"
        config.instructions = "Do everything"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        mcp_tool = FunctionTool(name="mcp::search", description="MCP search tool")
        agent_tool = FunctionTool(name="sub-agent", description="Agent-as-Tool")
        tg_tool = FunctionTool(name="tg::weather", description="ToolGroup weather", group="travel")

        all_tools = [mcp_tool, agent_tool, tg_tool]
        agent = _build_agent_from_config(config, mcp_tools=all_tools)

        assert len(agent.tools) == 3
        tool_names = {t.name for t in agent.tools}
        assert tool_names == {"mcp::search", "sub-agent", "tg::weather"}

    def test_with_guardrails_and_handoffs(self) -> None:
        """Guardrail 规则 + Handoff 目标同时配置。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "triage"
        config.description = "Triage agent"
        config.instructions = "Route requests"
        config.model = "gpt-4o"
        config.model_settings = {"temperature": 0.3}
        config.guardrails = None
        config.approval_mode = "suggest"

        # Guardrail 规则
        rule = MagicMock()
        rule.type = "input"
        rule.mode = "keyword"
        rule.name = "safety"
        rule.config = {"keywords": ["危险", "违法"], "message": "内容不安全"}

        # Handoff 目标
        from ckyclaw_framework.agent.agent import Agent as FrameworkAgent
        expert = FrameworkAgent(name="expert")

        agent = _build_agent_from_config(
            config,
            guardrail_rules=[rule],
            handoff_agents=[expert],
            mcp_tools=[],
        )

        assert agent.name == "triage"
        assert len(agent.input_guardrails) == 1
        assert agent.input_guardrails[0].name == "safety"
        assert len(agent.handoffs) == 1

    def test_empty_config(self) -> None:
        """最小配置也应成功构建 Agent。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "minimal"
        config.description = ""
        config.instructions = ""
        config.model = None
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        agent = _build_agent_from_config(config)
        assert agent.name == "minimal"
        assert agent.tools == []
        assert agent.handoffs == []
        assert agent.input_guardrails == []


# ---------------------------------------------------------------------------
# 三路工具解析综合测试
# ---------------------------------------------------------------------------


class TestThreeWayToolResolution:
    """验证 MCP + Agent-as-Tool + ToolGroup 三路工具解析的正确性。"""

    @pytest.mark.asyncio
    async def test_resolve_all_three_tool_sources(self) -> None:
        """三路工具源全部配置时，所有工具都应被解析。"""
        from app.services.session import _resolve_agent_tools, _resolve_tool_groups

        # 1. ToolGroup 解析
        config = MagicMock()
        config.name = "test-agent"
        config.tool_groups = ["search", "file-ops"]

        tg1 = MagicMock()
        tg1.name = "search"
        tg1.tools = [{"name": "web_search", "description": "Search", "parameters_schema": {}}]

        tg2 = MagicMock()
        tg2.name = "file-ops"
        tg2.tools = [{"name": "read_file", "description": "Read", "parameters_schema": {}}]

        db_tg = AsyncMock()
        mock_result_tg = MagicMock()
        mock_result_tg.scalars.return_value.all.return_value = [tg1, tg2]
        db_tg.execute = AsyncMock(return_value=mock_result_tg)

        tg_tools = await _resolve_tool_groups(db_tg, config)
        assert len(tg_tools) == 2

        # 2. Agent-as-Tool 解析
        config2 = MagicMock()
        config2.name = "manager"
        config2.agent_tools = ["analyst"]

        target_config = MagicMock()
        target_config.name = "analyst"
        target_config.description = "Analyst"
        target_config.instructions = "Analyze data"
        target_config.model = "gpt-4o"
        target_config.model_settings = None
        target_config.guardrails = None
        target_config.approval_mode = None
        target_config.handoffs = []
        target_config.agent_tools = []

        db_at = AsyncMock()
        mock_result_at = MagicMock()
        mock_result_at.scalars.return_value.all.return_value = [target_config]
        db_at.execute = AsyncMock(return_value=mock_result_at)

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            agent_tools = await _resolve_agent_tools(db_at, config2)

        assert len(agent_tools) == 1

        # 3. MCP 工具 (mock)
        mcp_tools = [FunctionTool(name="mcp::translate", description="Translate text")]

        # 合并
        all_tools = mcp_tools + agent_tools + tg_tools
        assert len(all_tools) == 4

        tool_names = {t.name for t in all_tools}
        assert tool_names == {"mcp::translate", "analyst", "web_search", "read_file"}

    @pytest.mark.asyncio
    async def test_partial_tool_sources(self) -> None:
        """仅部分工具源配置时，不影响其他源。"""
        from app.services.session import _resolve_tool_groups

        # 只有 ToolGroup，无 MCP / Agent-as-Tool
        config = MagicMock()
        config.name = "simple-agent"
        config.tool_groups = ["calculator"]

        tg = MagicMock()
        tg.name = "calculator"
        tg.tools = [{"name": "add", "description": "Add numbers", "parameters_schema": {}}]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tg]
        db.execute = AsyncMock(return_value=mock_result)

        tg_tools = await _resolve_tool_groups(db, config)
        mcp_tools: list[FunctionTool] = []
        agent_tools: list[FunctionTool] = []

        all_tools = mcp_tools + agent_tools + tg_tools
        assert len(all_tools) == 1
        assert all_tools[0].name == "add"


# ---------------------------------------------------------------------------
# _resolve_handoff_agents + _resolve_agent_tools 交叉测试
# ---------------------------------------------------------------------------


class TestHandoffAgentToolCross:
    """验证 Handoff 和 Agent-as-Tool 在同一 Agent 上协作的场景。"""

    @pytest.mark.asyncio
    async def test_agent_with_both_handoff_and_agent_tools(self) -> None:
        """同一 Agent 同时配置 handoffs 和 agent_tools。"""
        from app.services.session import _resolve_agent_tools, _resolve_handoff_agents

        # Handoff 目标
        handoff_config = MagicMock()
        handoff_config.name = "expert"
        handoff_config.description = "Expert"
        handoff_config.instructions = "Expert instructions"
        handoff_config.model = "gpt-4o"
        handoff_config.model_settings = None
        handoff_config.guardrails = None
        handoff_config.approval_mode = None
        handoff_config.handoffs = []
        handoff_config.agent_tools = []

        # Agent-as-Tool 目标
        tool_agent_config = MagicMock()
        tool_agent_config.name = "searcher"
        tool_agent_config.description = "Search engine"
        tool_agent_config.instructions = "Search things"
        tool_agent_config.model = "gpt-4o"
        tool_agent_config.model_settings = None
        tool_agent_config.guardrails = None
        tool_agent_config.approval_mode = None
        tool_agent_config.handoffs = []
        tool_agent_config.agent_tools = []

        triage_config = MagicMock()
        triage_config.name = "triage"
        triage_config.handoffs = ["expert"]
        triage_config.agent_tools = ["searcher"]

        # Mock DB - 为两次不同查询返回不同结果
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # handoff 查询
                result.scalars.return_value.all.return_value = [handoff_config]
            else:
                # agent_tools 查询
                result.scalars.return_value.all.return_value = [tool_agent_config]
            return result

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            handoffs = await _resolve_handoff_agents(db, triage_config)
            agent_tools = await _resolve_agent_tools(db, triage_config)

        assert len(handoffs) == 1
        assert handoffs[0].agent.name == "expert"
        assert len(agent_tools) == 1
        assert agent_tools[0].name == "searcher"

    @pytest.mark.asyncio
    async def test_different_targets_no_confusion(self) -> None:
        """Handoff 目标和 Agent-as-Tool 目标不互相干扰。"""
        from app.services.session import _resolve_agent_tools

        config = MagicMock()
        config.name = "hub"
        config.agent_tools = ["worker-a", "worker-b"]

        worker_a = MagicMock()
        worker_a.name = "worker-a"
        worker_a.description = "Worker A"
        worker_a.instructions = "Do A"
        worker_a.model = "gpt-4o"
        worker_a.model_settings = None
        worker_a.guardrails = None
        worker_a.approval_mode = None
        worker_a.handoffs = []
        worker_a.agent_tools = []

        worker_b = MagicMock()
        worker_b.name = "worker-b"
        worker_b.description = "Worker B"
        worker_b.instructions = "Do B"
        worker_b.model = "gpt-4o"
        worker_b.model_settings = None
        worker_b.guardrails = None
        worker_b.approval_mode = None
        worker_b.handoffs = []
        worker_b.agent_tools = []

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [worker_a, worker_b]
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.guardrail.get_guardrail_rules_by_names", new_callable=AsyncMock, return_value=[]):
            tools = await _resolve_agent_tools(db, config)

        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"worker-a", "worker-b"}

        # 每个 tool 都应是独立的 FunctionTool
        for t in tools:
            assert isinstance(t, FunctionTool)


# ---------------------------------------------------------------------------
# Guardrail + ToolGroup + Agent-as-Tool 综合构建测试
# ---------------------------------------------------------------------------


class TestCombinedBuild:
    """验证综合场景下 Agent 构建的正确性。"""

    def test_full_featured_agent_build(self) -> None:
        """构建拥有所有特性的 Agent：Guardrail + Handoff + Tools(三路)。"""
        from app.services.session import _build_agent_from_config
        from ckyclaw_framework.agent.agent import Agent as FrameworkAgent

        config = MagicMock()
        config.name = "full-agent"
        config.description = "Full featured"
        config.instructions = "You handle everything"
        config.model = "gpt-4o-mini"
        config.model_settings = {"temperature": 0.5, "max_tokens": 2000}
        config.guardrails = None
        config.approval_mode = "suggest"

        # Guardrail 规则
        rule = MagicMock()
        rule.type = "input"
        rule.mode = "regex"
        rule.name = "sql-injection"
        rule.config = {"patterns": [r"DROP\s+TABLE", r"DELETE\s+FROM"], "message": "SQL 注入检测"}

        # Handoff
        expert = FrameworkAgent(name="expert")

        # 三路工具
        mcp_tool = FunctionTool(name="mcp::api", description="MCP API tool")
        agent_tool = FunctionTool(name="sub-agent", description="Sub agent tool")
        tg_tool = FunctionTool(name="web_search", description="Web search", group="search")

        agent = _build_agent_from_config(
            config,
            guardrail_rules=[rule],
            handoff_agents=[expert],
            mcp_tools=[mcp_tool, agent_tool, tg_tool],
        )

        assert agent.name == "full-agent"
        assert len(agent.tools) == 3
        assert len(agent.input_guardrails) == 1
        assert agent.input_guardrails[0].name == "sql-injection"
        assert len(agent.handoffs) == 1
        assert agent.model == "gpt-4o-mini"
        assert agent.model_settings is not None
        assert agent.model_settings.temperature == 0.5

    def test_guardrail_types_regex_and_keyword(self) -> None:
        """支持 regex 和 keyword 两种 Guardrail 类型。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "guarded"
        config.description = ""
        config.instructions = ""
        config.model = None
        config.model_settings = None
        config.guardrails = None
        config.approval_mode = None

        rule_regex = MagicMock()
        rule_regex.type = "input"
        rule_regex.mode = "regex"
        rule_regex.name = "regex-guard"
        rule_regex.config = {"patterns": [r"\d{16}"], "message": "检测到信用卡号"}

        rule_keyword = MagicMock()
        rule_keyword.type = "input"
        rule_keyword.mode = "keyword"
        rule_keyword.name = "keyword-guard"
        rule_keyword.config = {"keywords": ["暴力", "违禁"], "message": "包含违禁词"}

        # 非 input 类型的规则应被忽略
        rule_output = MagicMock()
        rule_output.type = "output"
        rule_output.mode = "regex"
        rule_output.name = "output-guard"
        rule_output.config = {"patterns": [r".*"]}

        agent = _build_agent_from_config(
            config,
            guardrail_rules=[rule_regex, rule_keyword, rule_output],
        )

        # 只有 input 类型的 guardrail 被添加
        assert len(agent.input_guardrails) == 2
        guard_names = {g.name for g in agent.input_guardrails}
        assert guard_names == {"regex-guard", "keyword-guard"}


# ---------------------------------------------------------------------------
# Token Usage 提取测试
# ---------------------------------------------------------------------------


class TestTokenUsageExtraction:
    @pytest.mark.asyncio
    async def test_save_token_usage_from_trace(self) -> None:
        """从 trace 中正确提取 LLM span 的 token_usage。"""
        from app.services.session import _save_token_usage_from_trace

        # 构造 mock trace
        llm_span1 = MagicMock()
        llm_span1.type = "llm"
        llm_span1.span_id = "span-1"
        llm_span1.name = "gpt-4o"
        llm_span1.model = "gpt-4o"
        llm_span1.parent_span_id = "agent-span-1"
        llm_span1.token_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        llm_span2 = MagicMock()
        llm_span2.type = "llm"
        llm_span2.span_id = "span-2"
        llm_span2.name = "gpt-4o"
        llm_span2.model = "gpt-4o"
        llm_span2.parent_span_id = "agent-span-2"
        llm_span2.token_usage = {"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110}

        agent_span1 = MagicMock()
        agent_span1.type = "agent"
        agent_span1.span_id = "agent-span-1"
        agent_span1.name = "main-agent"

        agent_span2 = MagicMock()
        agent_span2.type = "agent"
        agent_span2.span_id = "agent-span-2"
        agent_span2.name = "sub-agent"

        tool_span = MagicMock()
        tool_span.type = "tool"
        tool_span.span_id = "tool-span-1"
        tool_span.token_usage = None  # tool span 没有 token_usage

        trace = MagicMock()
        trace.trace_id = "trace-001"
        trace.spans = [agent_span1, llm_span1, tool_span, agent_span2, llm_span2]

        db = AsyncMock()

        import uuid
        session_id = uuid.uuid4()

        await _save_token_usage_from_trace(db, trace, session_id=session_id)

        # 应该添加了 2 条 token_usage_log
        assert db.add_all.called
        logs = db.add_all.call_args[0][0]
        assert len(logs) == 2
        assert logs[0].prompt_tokens == 100
        assert logs[0].total_tokens == 150
        assert logs[0].agent_name == "main-agent"
        assert logs[1].prompt_tokens == 80
        assert logs[1].agent_name == "sub-agent"

    @pytest.mark.asyncio
    async def test_save_token_usage_none_trace(self) -> None:
        """trace 为 None 时不执行任何操作。"""
        from app.services.session import _save_token_usage_from_trace

        db = AsyncMock()
        await _save_token_usage_from_trace(db, None)
        assert not db.add_all.called

    @pytest.mark.asyncio
    async def test_save_token_usage_no_llm_spans(self) -> None:
        """trace 中没有 LLM span 时不写入记录。"""
        from app.services.session import _save_token_usage_from_trace

        trace = MagicMock()
        trace.trace_id = "trace-002"

        # 只有 agent span，没有 llm span
        agent_span = MagicMock()
        agent_span.type = "agent"
        agent_span.token_usage = None

        trace.spans = [agent_span]

        db = AsyncMock()
        await _save_token_usage_from_trace(db, trace)
        # 没有 LLM span，不 add_all（或 add_all 空列表被跳过）
        # _save_token_usage_from_trace 只在 logs 非空时才调用 add_all
        if db.add_all.called:
            logs = db.add_all.call_args[0][0]
            assert len(logs) == 0


# ---------------------------------------------------------------------------
# _find_parent_agent_name 测试
# ---------------------------------------------------------------------------


class TestFindParentAgentName:
    def test_finds_parent_agent(self) -> None:
        from app.services.session import _find_parent_agent_name

        agent_span = MagicMock()
        agent_span.type = "agent"
        agent_span.span_id = "agent-1"
        agent_span.name = "my-agent"

        llm_span = MagicMock()
        llm_span.type = "llm"
        llm_span.span_id = "llm-1"
        llm_span.parent_span_id = "agent-1"

        result = _find_parent_agent_name([agent_span, llm_span], llm_span)
        assert result == "my-agent"

    def test_no_parent(self) -> None:
        from app.services.session import _find_parent_agent_name

        llm_span = MagicMock()
        llm_span.type = "llm"
        llm_span.span_id = "llm-1"
        llm_span.parent_span_id = None

        result = _find_parent_agent_name([llm_span], llm_span)
        assert result is None

    def test_parent_not_agent_type(self) -> None:
        from app.services.session import _find_parent_agent_name

        tool_span = MagicMock()
        tool_span.type = "tool"
        tool_span.span_id = "tool-1"
        tool_span.name = "some-tool"

        llm_span = MagicMock()
        llm_span.type = "llm"
        llm_span.span_id = "llm-1"
        llm_span.parent_span_id = "tool-1"

        result = _find_parent_agent_name([tool_span, llm_span], llm_span)
        assert result is None


# ---------------------------------------------------------------------------
# E2E — 新功能端点综合验证
#   rotate-key / checkpoint CRUD / cost-router classify+recommend
# ---------------------------------------------------------------------------


class TestE2ENewEndpoints:
    """跨 API 端到端验证——使用 TestClient + mock service/DB 层。"""

    @pytest.fixture()
    def client(self) -> TestClient:
        from fastapi.testclient import TestClient as TC

        from app.main import app as _app

        return TC(_app)

    # ---- rotate-key ----

    def test_rotate_key_flow(self, client: TestClient) -> None:
        """rotate-key → 响应包含更新后时间戳。"""
        import uuid
        from datetime import datetime

        pid = uuid.uuid4()
        now = datetime.now(UTC)

        p = MagicMock()
        p.id = pid
        p.name = "test"
        p.provider_type = "openai"
        p.base_url = "https://api.openai.com/v1"
        p.api_key_encrypted = "enc"
        p.auth_type = "api_key"
        p.auth_config = {}
        p.rate_limit_rpm = None
        p.rate_limit_tpm = None
        p.is_enabled = True
        p.org_id = None
        p.last_health_check = None
        p.health_status = "unknown"
        p.key_expires_at = None
        p.key_last_rotated_at = now
        p.model_tier = "moderate"
        p.capabilities = []
        p.created_at = now
        p.updated_at = now

        with patch("app.api.providers.provider_service.rotate_key", new_callable=AsyncMock, return_value=p):
            resp = client.post(
                f"/api/v1/providers/{pid}/rotate-key",
                json={"new_api_key": "sk-new-key-12345"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["key_last_rotated_at"] is not None
        assert body["key_expired"] is False

    # ---- checkpoint CRUD (mock DB) ----

    def _mock_db(self) -> AsyncMock:
        """创建 mock AsyncSession。"""
        db = AsyncMock()
        return db

    def test_checkpoint_list_empty(self, client: TestClient) -> None:
        """查询不存在的 run_id 返回空列表。"""
        from app.core.deps import get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        # mock count = 0, rows = []
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=0)),  # count
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # data
        ])

        async def _fake_db():
            yield mock_db

        _app.dependency_overrides[get_db] = _fake_db
        try:
            resp = client.get("/api/v1/checkpoints?run_id=nonexistent")
            assert resp.status_code == 200
            body = resp.json()
            assert body["data"] == []
            assert body["total"] == 0
        finally:
            _app.dependency_overrides.pop(get_db, None)

    def test_checkpoint_delete(self, client: TestClient) -> None:
        """删除检查点返回 204。"""
        from app.core.deps import get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        # delete needs: PostgresCheckpointBackend constructor + delete + commit
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.commit = AsyncMock()

        async def _fake_db():
            yield mock_db

        _app.dependency_overrides[get_db] = _fake_db
        try:
            resp = client.delete("/api/v1/checkpoints/run-e2e")
            assert resp.status_code == 204
        finally:
            _app.dependency_overrides.pop(get_db, None)

    # ---- cost-router classify ----

    def test_cost_router_classify(self, client: TestClient) -> None:
        """classify 端点返回分类层级。"""
        with patch("app.api.cost_router.classify_complexity") as mock_classify:
            from ckyclaw_framework.model.cost_router import ModelTier

            mock_classify.return_value = ModelTier.MODERATE
            resp = client.post(
                "/api/v1/cost-router/classify",
                json={"text": "帮我写一个 Python 排序算法"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == "moderate"
        assert body["text_length"] > 0

    def test_cost_router_recommend(self, client: TestClient) -> None:
        """recommend 端点通过 DB 查询 Provider 并返回推荐。"""
        from app.core.deps import get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        # mock: no providers in DB → recommend returns None
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _fake_db():
            yield mock_db

        _app.dependency_overrides[get_db] = _fake_db
        try:
            resp = client.post(
                "/api/v1/cost-router/recommend",
                json={"text": "分析这张图片的内容"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["tier"] in ("simple", "moderate", "complex", "reasoning", "multimodal")
            # 没有 providers → provider_name = null
            assert body["provider_name"] is None
        finally:
            _app.dependency_overrides.pop(get_db, None)

    # ---- intent detect ----

    def test_intent_detect_no_drift(self, client: TestClient) -> None:
        """相同主题 → 飘移分数低，不飘移。"""
        from app.core.deps import get_current_user
        from app.main import app as _app

        _app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        try:
            resp = client.post(
                "/api/v1/intent/detect",
                json={
                    "original_intent": "帮我写一个 Python 排序算法",
                    "current_message": "用快速排序实现",
                    "threshold": 0.6,
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_drifted"] is False
            assert body["drift_score"] < 0.6
            assert len(body["original_keywords"]) > 0
            assert len(body["current_keywords"]) > 0
        finally:
            _app.dependency_overrides.pop(get_current_user, None)

    def test_intent_detect_drifted(self, client: TestClient) -> None:
        """完全不同主题 → 飘移分数高，判定飘移。"""
        from app.core.deps import get_current_user
        from app.main import app as _app

        _app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        try:
            resp = client.post(
                "/api/v1/intent/detect",
                json={
                    "original_intent": "帮我写一个 Python 排序算法",
                    "current_message": "今天北京天气怎么样",
                    "threshold": 0.3,
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_drifted"] is True
            assert body["drift_score"] > 0.3
        finally:
            _app.dependency_overrides.pop(get_current_user, None)

    def test_intent_detect_validation(self, client: TestClient) -> None:
        """缺少必填字段返回 422。"""
        from app.core.deps import get_current_user
        from app.main import app as _app

        _app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        try:
            resp = client.post(
                "/api/v1/intent/detect",
                json={"original_intent": "hello"},
            )
            assert resp.status_code == 422
        finally:
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- deep health check ----

    def test_deep_health_check(self, client: TestClient) -> None:
        """深度健康检查返回 components 结构。"""
        resp = client.get("/health/deep")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "components" in body
        assert "database" in body["components"]
        assert "redis" in body["components"]

    # ---- token usage trend ----

    def test_token_usage_trend(self, client: TestClient) -> None:
        """Token 趋势 API 返回正确结构。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )

        # require_permission 需要 User 对象（role_id / role 属性）
        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/token-usage/trend", params={"days": 7})
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert "days" in body
            assert body["days"] == 7
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- agent realtime status ----

    def test_agent_realtime_status(self, client: TestClient) -> None:
        """Agent 实时状态 API 返回正确结构。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/agents/realtime-status", params={"minutes": 5})
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert "minutes" in body
            assert body["minutes"] == 5
            assert isinstance(body["data"], list)
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_agent_realtime_status_invalid_minutes(self, client: TestClient) -> None:
        """minutes 超范围返回 422。"""
        from app.core.deps import get_current_user
        from app.main import app as _app

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/agents/realtime-status", params={"minutes": 100})
            assert resp.status_code == 422
        finally:
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- agent activity trend ----

    def test_agent_activity_trend(self, client: TestClient) -> None:
        """Agent 活动趋势 API 返回正确结构。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get(
                "/api/v1/agents/activity-trend",
                params={"hours": 1, "interval": 5},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert body["hours"] == 1
            assert body["interval"] == 5
            assert isinstance(body["data"], list)
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_agent_activity_trend_invalid_hours(self, client: TestClient) -> None:
        """hours 超范围返回 422。"""
        from app.core.deps import get_current_user
        from app.main import app as _app

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get(
                "/api/v1/agents/activity-trend",
                params={"hours": 100},
            )
            assert resp.status_code == 422
        finally:
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- template instantiate ----

    def test_template_instantiate(self, client: TestClient) -> None:
        """模板实例化 API 返回合并后的配置。"""
        import uuid

        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        template = MagicMock()
        template.id = uuid.uuid4()
        template.name = "test-tpl"
        template.display_name = "测试模板"
        template.description = "测试描述"
        template.category = "general"
        template.is_deleted = False
        template.config = {"instructions": "默认指令", "tools": []}

        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=template))
        )

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.post(
                f"/api/v1/agent-templates/{template.id}/instantiate",
                json={"instructions": "自定义指令"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["template_name"] == "test-tpl"
            assert body["config"]["instructions"] == "自定义指令"
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_template_instantiate_no_overrides(self, client: TestClient) -> None:
        """无覆盖参数实例化返回原始配置。"""
        import uuid

        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        template = MagicMock()
        template.id = uuid.uuid4()
        template.name = "test-tpl2"
        template.display_name = "测试模板2"
        template.description = "描述2"
        template.category = "analytics"
        template.is_deleted = False
        template.config = {"instructions": "原始指令", "handoffs": ["a"]}

        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=template))
        )

        fake_user = MagicMock()
        fake_user.role_id = None
        fake_user.role = "admin"

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.post(
                f"/api/v1/agent-templates/{template.id}/instantiate",
                content="null",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["config"]["instructions"] == "原始指令"
            assert body["config"]["handoffs"] == ["a"]
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- R15: trace flame tree ----

    def test_trace_flame_tree(self, client: TestClient) -> None:
        """火焰图 API 返回嵌套 Span 树结构。"""
        from datetime import datetime

        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()

        # mock trace
        trace_obj = MagicMock()
        trace_obj.id = "trace-flame-001"
        trace_obj.status = "completed"

        now = datetime.now(UTC)
        root_span = MagicMock()
        root_span.id = "span-root"
        root_span.trace_id = "trace-flame-001"
        root_span.parent_span_id = None
        root_span.type = "agent"
        root_span.name = "root-agent"
        root_span.status = "completed"
        root_span.start_time = now
        root_span.end_time = now
        root_span.duration_ms = 100
        root_span.model = "gpt-4o"

        child_span = MagicMock()
        child_span.id = "span-child"
        child_span.trace_id = "trace-flame-001"
        child_span.parent_span_id = "span-root"
        child_span.type = "llm"
        child_span.name = "llm-call"
        child_span.status = "completed"
        child_span.start_time = now
        child_span.end_time = now
        child_span.duration_ms = 80
        child_span.model = "gpt-4o"

        call_count = [0]

        def _mock_execute(*args: object, **kwargs: object) -> MagicMock:
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=trace_obj)
            else:
                result.scalars = MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[root_span, child_span]))
                )
            return result

        mock_db.execute = AsyncMock(side_effect=_mock_execute)

        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/traces/trace-flame-001/flame")
            assert resp.status_code == 200
            body = resp.json()
            assert body["trace_id"] == "trace-flame-001"
            assert body["total_spans"] == 2
            root = body["root"]
            assert root["span_id"] == "span-root"
            assert root["type"] == "agent"
            assert len(root["children"]) == 1
            assert root["children"][0]["span_id"] == "span-child"
            assert root["children"][0]["type"] == "llm"
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_trace_flame_tree_max_depth(self, client: TestClient) -> None:
        """火焰图 max_depth 参数校验 — 超出范围返回 422。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/traces/any-id/flame", params={"max_depth": 0})
            assert resp.status_code == 422
            resp2 = client.get("/api/v1/traces/any-id/flame", params={"max_depth": 200})
            assert resp2.status_code == 422
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- R15: session message search ----

    def test_session_message_search(self, client: TestClient) -> None:
        """Session 消息搜索 — search 参数正确传递到查询。"""
        import uuid

        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        session_id = uuid.uuid4()
        mock_db = self._mock_db()

        session_obj = MagicMock()
        session_obj.id = session_id

        msg = MagicMock()
        msg.id = 1
        msg.role = "user"
        msg.content = "搜索关键词匹配"
        msg.agent_name = None
        msg.tool_call_id = None
        msg.tool_calls = None
        msg.token_usage = None
        msg.created_at = "2025-01-01T00:00:00Z"

        call_count = [0]

        def _mock_execute(*args: object, **kwargs: object) -> MagicMock:
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=session_obj)
            else:
                result.scalars = MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[msg]))
                )
            return result

        mock_db.execute = AsyncMock(side_effect=_mock_execute)

        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get(
                f"/api/v1/sessions/{session_id}/messages",
                params={"search": "关键词"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] >= 0
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- R15: WebSocket events endpoint registered ----

    def test_ws_events_endpoint_exists(self, client: TestClient) -> None:
        """验证 /api/ws/events WebSocket 端点已注册。"""
        from app.main import app as _app

        ws_routes = [r.path for r in _app.routes if hasattr(r, "path")]
        assert "/api/ws/events" in ws_routes

    # ---- R16: Trace 回放时间轴 ----

    def test_trace_replay_timeline(self, client: TestClient) -> None:
        """回放时间轴 API 返回正确的 timeline 结构。"""
        import datetime as _dt

        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()

        now = _dt.datetime(2025, 1, 1, 12, 0, 0)
        trace_obj = MagicMock()
        trace_obj.id = "trace-replay-001"
        trace_obj.duration_ms = 500

        span_a = MagicMock()
        span_a.id = "span-a"
        span_a.parent_span_id = None
        span_a.type = "agent"
        span_a.name = "root-agent"
        span_a.status = "completed"
        span_a.start_time = now
        span_a.end_time = now + _dt.timedelta(milliseconds=500)
        span_a.duration_ms = 500
        span_a.model = None
        span_a.input_data = '{"msg":"hi"}'
        span_a.output_data = '{"msg":"bye"}'

        span_b = MagicMock()
        span_b.id = "span-b"
        span_b.parent_span_id = "span-a"
        span_b.type = "llm"
        span_b.name = "gpt-4o"
        span_b.status = "completed"
        span_b.start_time = now + _dt.timedelta(milliseconds=100)
        span_b.end_time = now + _dt.timedelta(milliseconds=400)
        span_b.duration_ms = 300
        span_b.model = "gpt-4o"
        span_b.input_data = None
        span_b.output_data = "hello world"

        call_count = [0]

        def _mock_execute(*args: object, **kwargs: object) -> MagicMock:
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=trace_obj)
            else:
                result.scalars = MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[span_a, span_b]))
                )
            return result

        mock_db.execute = AsyncMock(side_effect=_mock_execute)

        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/traces/trace-replay-001/replay")
            assert resp.status_code == 200
            body = resp.json()
            assert body["trace_id"] == "trace-replay-001"
            assert body["total_duration_ms"] == 500
            tl = body["timeline"]
            assert len(tl) == 2
            assert tl[0]["span_id"] == "span-a"
            assert tl[0]["offset_ms"] == 0
            assert tl[0]["type"] == "agent"
            assert tl[1]["span_id"] == "span-b"
            assert tl[1]["offset_ms"] == 100
            assert tl[1]["type"] == "llm"
            assert tl[1]["model"] == "gpt-4o"
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_trace_replay_not_found(self, client: TestClient) -> None:
        """不存在的 Trace 回放返回 404。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.get("/api/v1/traces/nonexistent/replay")
            assert resp.status_code == 404
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- R16: A/B 测试 ----

    def test_ab_test_validation(self, client: TestClient) -> None:
        """A/B 测试模型数 <2 返回 422。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user
        try:
            resp = client.post(
                "/api/v1/ab-test",
                json={"prompt": "hello", "models": ["gpt-4o"]},
            )
            assert resp.status_code == 422
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    def test_ab_test_success(self, client: TestClient) -> None:
        """A/B 测试正常返回对比结果（mock LLM）。"""
        from app.core.deps import get_current_user, get_db
        from app.main import app as _app

        mock_db = self._mock_db()
        # _resolve_provider_kwargs: 不返回 provider
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        fake_user = MagicMock(role_id=None, role="admin")
        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: fake_user

        mock_response = MagicMock()
        mock_response.content = "Hello from mock"
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30
        mock_response.usage = mock_usage

        try:
            with patch(
                "ckyclaw_framework.model.litellm_provider.LiteLLMProvider",
            ) as MockProvider:
                instance = MockProvider.return_value
                instance.chat = AsyncMock(return_value=mock_response)
                resp = client.post(
                    "/api/v1/ab-test",
                    json={"prompt": "你好", "models": ["gpt-4o", "claude-3"]},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["prompt"] == "你好"
            assert len(body["results"]) == 2
            for r in body["results"]:
                assert r["output"] == "Hello from mock"
                assert r["latency_ms"] >= 0
                assert r["token_usage"]["total_tokens"] == 30
                assert r["error"] is None
        finally:
            _app.dependency_overrides.pop(get_db, None)
            _app.dependency_overrides.pop(get_current_user, None)

    # ---- Marketplace 端到端 ----

    def test_marketplace_browse_and_install(self, client: TestClient) -> None:
        """Marketplace 浏览 + 安装 端到端流程。"""
        import uuid
        from datetime import datetime


        now = datetime.now(UTC)
        tpl_id = uuid.uuid4()
        tpl = MagicMock()
        for k, v in {
            "id": tpl_id, "name": "demo-tpl", "display_name": "Demo",
            "description": "A demo template", "category": "general", "icon": "robot",
            "published": True, "downloads": 5, "rating": 4.0, "rating_count": 1,
            "author_org_id": None, "is_builtin": False,
            "config": {"instructions": "hi"}, "is_deleted": False,
            "created_at": now, "updated_at": now,
        }.items():
            setattr(tpl, k, v)

        with patch("app.api.marketplace.mp_svc") as mock_svc:
            mock_svc.list_marketplace = AsyncMock(return_value=([tpl], 1))
            mock_svc.install_template = AsyncMock(return_value=MagicMock(
                id=uuid.uuid4(), name="my-agent", created_at=now, updated_at=now,
            ))

            # 浏览
            resp = client.get("/api/v1/marketplace")
            assert resp.status_code == 200
            assert resp.json()["total"] == 1
            assert resp.json()["data"][0]["name"] == "demo-tpl"

            # 安装
            resp2 = client.post(
                f"/api/v1/marketplace/{tpl_id}/install",
                json={"agent_name": "my-installed-agent"},
            )
            assert resp2.status_code == 200

    def test_marketplace_review_flow(self, client: TestClient) -> None:
        """Marketplace 评价流程。"""
        import uuid
        from datetime import datetime

        tpl_id = uuid.uuid4()
        now = datetime.now(UTC)
        review = MagicMock()
        for k, v in {
            "id": uuid.uuid4(), "template_id": tpl_id,
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "score": 5, "comment": "Excellent!", "is_deleted": False, "created_at": now,
        }.items():
            setattr(review, k, v)

        with patch("app.api.marketplace.mp_svc") as mock_svc:
            mock_svc.create_review = AsyncMock(return_value=review)
            mock_svc.list_reviews = AsyncMock(return_value=([review], 1))

            resp = client.post(
                f"/api/v1/marketplace/{tpl_id}/reviews",
                json={"score": 5, "comment": "Excellent!"},
            )
            assert resp.status_code == 201

            resp2 = client.get(f"/api/v1/marketplace/{tpl_id}/reviews")
            assert resp2.status_code == 200
            assert resp2.json()["total"] == 1

    # ---- Compliance 端到端 ----

    def test_compliance_label_create_and_list(self, client: TestClient) -> None:
        """Compliance 数据分类标签创建 + 列表。"""
        import uuid
        from datetime import datetime

        now = datetime.now(UTC)
        label = MagicMock()
        for k, v in {
            "id": uuid.uuid4(), "resource_type": "trace", "resource_id": "t-123",
            "classification": "pii", "auto_detected": False, "reason": "email",
            "is_deleted": False, "created_at": now,
        }.items():
            setattr(label, k, v)

        with patch("app.api.compliance.comp_svc") as mock_svc:
            mock_svc.create_label = AsyncMock(return_value=label)
            mock_svc.list_labels = AsyncMock(return_value=([label], 1))

            resp = client.post("/api/v1/compliance/labels", json={
                "resource_type": "trace", "resource_id": "t-123", "classification": "pii",
            })
            assert resp.status_code == 201

            resp2 = client.get("/api/v1/compliance/labels")
            assert resp2.status_code == 200
            assert resp2.json()["total"] == 1

    def test_compliance_erasure_flow(self, client: TestClient) -> None:
        """Compliance 删除请求创建 + 处理。"""
        import uuid
        from datetime import datetime

        now = datetime.now(UTC)
        req_id = uuid.uuid4()
        erasure = MagicMock()
        for k, v in {
            "id": req_id, "requester_user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "target_user_id": uuid.uuid4(), "status": "pending",
            "scanned_resources": 0, "deleted_resources": 0, "report": None,
            "completed_at": None, "is_deleted": False, "created_at": now, "updated_at": now,
        }.items():
            setattr(erasure, k, v)

        completed = MagicMock()
        for k, v in {
            "id": req_id, "requester_user_id": erasure.requester_user_id,
            "target_user_id": erasure.target_user_id, "status": "completed",
            "scanned_resources": 100, "deleted_resources": 95,
            "report": {"details": "done"}, "completed_at": now,
            "is_deleted": False, "created_at": now, "updated_at": now,
        }.items():
            setattr(completed, k, v)

        with patch("app.api.compliance.comp_svc") as mock_svc:
            mock_svc.create_erasure_request = AsyncMock(return_value=erasure)
            mock_svc.process_erasure_request = AsyncMock(return_value=completed)

            resp = client.post("/api/v1/compliance/erasure-requests", json={
                "target_user_id": str(erasure.target_user_id),
            })
            assert resp.status_code == 201
            assert resp.json()["status"] == "pending"

            resp2 = client.post(
                f"/api/v1/compliance/erasure-requests/{req_id}/complete",
            )
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "completed"

    def test_compliance_dashboard(self, client: TestClient) -> None:
        """Compliance 仪表盘汇总。"""
        with patch("app.api.compliance.comp_svc") as mock_svc:
            mock_svc.get_dashboard = AsyncMock(return_value={
                "total_control_points": 20, "satisfied_control_points": 15,
                "satisfaction_rate": 0.75, "active_retention_policies": 5,
                "pending_erasure_requests": 2,
                "classification_summary": {"pii": 10, "internal": 30},
            })
            resp = client.get("/api/v1/compliance/dashboard")
            assert resp.status_code == 200
            body = resp.json()
            assert body["satisfaction_rate"] == 0.75
            assert body["classification_summary"]["pii"] == 10
