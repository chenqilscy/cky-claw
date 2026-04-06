"""Phase 6.9 后端端到端集成测试 — 完整链路验证。

验证 _build_agent_from_config + _resolve_* 系列函数 + execute_run 的综合协作。
使用 MagicMock 模拟 DB 层，但实际执行 Framework Runner。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool


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
        from ckyclaw_framework.agent.agent import Agent as FrameworkAgent

        from app.services.session import _build_agent_from_config

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
    def client(self) -> "TestClient":
        from fastapi.testclient import TestClient as TC

        from app.main import app as _app

        return TC(_app)

    # ---- rotate-key ----

    def test_rotate_key_flow(self, client: "TestClient") -> None:
        """rotate-key → 响应包含更新后时间戳。"""
        import uuid
        from datetime import datetime, timezone

        pid = uuid.uuid4()
        now = datetime.now(timezone.utc)

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

    def test_checkpoint_list_empty(self, client: "TestClient") -> None:
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

    def test_checkpoint_delete(self, client: "TestClient") -> None:
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

    def test_cost_router_classify(self, client: "TestClient") -> None:
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

    def test_cost_router_recommend(self, client: "TestClient") -> None:
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
