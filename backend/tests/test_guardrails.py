"""Guardrail 规则 CRUD + RegexGuardrail 测试。"""

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


def _make_guardrail_rule(**overrides: Any) -> MagicMock:
    """构造模拟 GuardrailRule ORM 对象。"""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-rule",
        "description": "测试规则",
        "type": "input",
        "mode": "regex",
        "config": {"patterns": [r"DROP\s+TABLE"], "message": "SQL 注入检测"},
        "conditions": {},
        "is_enabled": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ═══════════════════════════════════════════════════════════════════
# Schema 测试
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailSchemas:
    """Guardrail Schema 验证。"""

    def test_rule_response_model_validate(self) -> None:
        from app.schemas.guardrail import GuardrailRuleResponse

        mock = _make_guardrail_rule()
        resp = GuardrailRuleResponse.model_validate(mock)
        assert resp.name == "test-rule"
        assert resp.type == "input"
        assert resp.mode == "regex"

    def test_rule_create_valid(self) -> None:
        from app.schemas.guardrail import GuardrailRuleCreate

        data = GuardrailRuleCreate(
            name="sql-injection",
            type="input",
            mode="regex",
            config={"patterns": [r"DROP\s+TABLE"]},
        )
        assert data.name == "sql-injection"

    def test_rule_create_invalid_name(self) -> None:
        from app.schemas.guardrail import GuardrailRuleCreate

        with pytest.raises(Exception):
            GuardrailRuleCreate(name="Invalid Name!", type="input", mode="regex")

    def test_rule_create_invalid_type(self) -> None:
        from app.schemas.guardrail import GuardrailRuleCreate

        with pytest.raises(Exception):
            GuardrailRuleCreate(name="test-rule", type="invalid", mode="regex")

    def test_rule_create_invalid_mode(self) -> None:
        from app.schemas.guardrail import GuardrailRuleCreate

        with pytest.raises(Exception):
            GuardrailRuleCreate(name="test-rule", type="input", mode="magic")

    def test_rule_list_response(self) -> None:
        from app.schemas.guardrail import GuardrailRuleListResponse, GuardrailRuleResponse

        items = [GuardrailRuleResponse.model_validate(_make_guardrail_rule(name=f"rule-{i}")) for i in range(3)]
        resp = GuardrailRuleListResponse(data=items, total=10)
        assert len(resp.data) == 3
        assert resp.total == 10


# ═══════════════════════════════════════════════════════════════════
# API 端点测试
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailAPI:
    """Guardrail CRUD API 端点测试。"""

    @patch("app.api.guardrails.guardrail_service")
    def test_create_rule(self, mock_svc: MagicMock) -> None:
        """创建规则成功。"""
        rule = _make_guardrail_rule()
        mock_svc.create_guardrail_rule = AsyncMock(return_value=rule)

        client = TestClient(app)
        resp = client.post("/api/v1/guardrails", json={
            "name": "test-rule",
            "type": "input",
            "mode": "regex",
            "config": {"patterns": [r"DROP\s+TABLE"]},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-rule"

    @patch("app.api.guardrails.guardrail_service")
    def test_list_rules_empty(self, mock_svc: MagicMock) -> None:
        """空列表。"""
        mock_svc.list_guardrail_rules = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/guardrails")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    @patch("app.api.guardrails.guardrail_service")
    def test_list_rules_with_data(self, mock_svc: MagicMock) -> None:
        """列表含数据。"""
        rules = [_make_guardrail_rule(name=f"rule-{i}") for i in range(3)]
        mock_svc.list_guardrail_rules = AsyncMock(return_value=(rules, 3))

        client = TestClient(app)
        resp = client.get("/api/v1/guardrails")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3

    @patch("app.api.guardrails.guardrail_service")
    def test_list_rules_with_filters(self, mock_svc: MagicMock) -> None:
        """按 type 筛选。"""
        mock_svc.list_guardrail_rules = AsyncMock(return_value=([], 0))

        client = TestClient(app)
        resp = client.get("/api/v1/guardrails?type=input&enabled_only=true")
        assert resp.status_code == 200
        call_kwargs = mock_svc.list_guardrail_rules.call_args
        assert call_kwargs.kwargs["type_filter"] == "input"
        assert call_kwargs.kwargs["enabled_only"] is True

    @patch("app.api.guardrails.guardrail_service")
    def test_get_rule(self, mock_svc: MagicMock) -> None:
        """获取单个规则。"""
        rule_id = uuid.uuid4()
        rule = _make_guardrail_rule(id=rule_id)
        mock_svc.get_guardrail_rule = AsyncMock(return_value=rule)

        client = TestClient(app)
        resp = client.get(f"/api/v1/guardrails/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-rule"

    @patch("app.api.guardrails.guardrail_service")
    def test_get_rule_not_found(self, mock_svc: MagicMock) -> None:
        """规则不存在返回 404。"""
        from app.core.exceptions import NotFoundError

        mock_svc.get_guardrail_rule = AsyncMock(side_effect=NotFoundError("not found"))

        client = TestClient(app)
        resp = client.get(f"/api/v1/guardrails/{uuid.uuid4()}")
        assert resp.status_code == 404

    @patch("app.api.guardrails.guardrail_service")
    def test_update_rule(self, mock_svc: MagicMock) -> None:
        """更新规则。"""
        rule_id = uuid.uuid4()
        rule = _make_guardrail_rule(id=rule_id, description="updated")
        mock_svc.update_guardrail_rule = AsyncMock(return_value=rule)

        client = TestClient(app)
        resp = client.put(f"/api/v1/guardrails/{rule_id}", json={"description": "updated"})
        assert resp.status_code == 200

    @patch("app.api.guardrails.guardrail_service")
    def test_delete_rule(self, mock_svc: MagicMock) -> None:
        """删除规则。"""
        mock_svc.delete_guardrail_rule = AsyncMock(return_value=None)

        client = TestClient(app)
        resp = client.delete(f"/api/v1/guardrails/{uuid.uuid4()}")
        assert resp.status_code == 204


# ═══════════════════════════════════════════════════════════════════
# LLM 模式 Schema 验证测试
# ═══════════════════════════════════════════════════════════════════


class TestLLMModeSchemas:
    """LLM 模式 Guardrail Schema 测试。"""

    def test_create_llm_mode_accepted(self) -> None:
        """mode=llm 在 Schema 层应通过。"""
        from app.schemas.guardrail import GuardrailRuleCreate

        data = GuardrailRuleCreate(
            name="llm-injection-check",
            type="input",
            mode="llm",
            config={"preset": "prompt_injection"},
        )
        assert data.mode == "llm"

    def test_create_llm_custom_with_template(self) -> None:
        from app.schemas.guardrail import GuardrailRuleCreate

        data = GuardrailRuleCreate(
            name="llm-custom-rule",
            type="output",
            mode="llm",
            config={
                "preset": "custom",
                "prompt_template": "检查以下内容: {content}",
                "model": "gpt-4o-mini",
                "threshold": 0.85,
            },
        )
        assert data.mode == "llm"
        assert data.config["preset"] == "custom"

    def test_update_llm_mode_accepted(self) -> None:
        from app.schemas.guardrail import GuardrailRuleUpdate

        data = GuardrailRuleUpdate(mode="llm")
        assert data.mode == "llm"


# ═══════════════════════════════════════════════════════════════════
# LLM 模式 Service _validate_config 测试
# ═══════════════════════════════════════════════════════════════════


class TestLLMModeValidation:
    """LLM 模式 _validate_config 逻辑测试。"""

    def test_valid_prompt_injection_preset(self) -> None:
        from app.services.guardrail import _validate_config

        _validate_config("llm", {"preset": "prompt_injection"})

    def test_valid_content_safety_preset(self) -> None:
        from app.services.guardrail import _validate_config

        _validate_config("llm", {"preset": "content_safety"})

    def test_valid_custom_preset(self) -> None:
        from app.services.guardrail import _validate_config

        _validate_config("llm", {
            "preset": "custom",
            "prompt_template": "请判断以下内容是否安全: {content}",
        })

    def test_invalid_preset(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="preset"):
            _validate_config("llm", {"preset": "unknown_preset"})

    def test_custom_without_template_raises(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="prompt_template"):
            _validate_config("llm", {"preset": "custom"})

    def test_custom_template_missing_placeholder(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="prompt_template"):
            _validate_config("llm", {
                "preset": "custom",
                "prompt_template": "检查内容",
            })

    def test_threshold_out_of_range(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="threshold"):
            _validate_config("llm", {"preset": "prompt_injection", "threshold": 1.5})

    def test_threshold_negative(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="threshold"):
            _validate_config("llm", {"preset": "prompt_injection", "threshold": -0.1})

    def test_model_not_string(self) -> None:
        from app.services.guardrail import _validate_config

        with pytest.raises(Exception, match="model"):
            _validate_config("llm", {"preset": "prompt_injection", "model": 123})

    def test_valid_with_all_options(self) -> None:
        """完整 LLM 配置应通过验证。"""
        from app.services.guardrail import _validate_config

        _validate_config("llm", {
            "preset": "custom",
            "prompt_template": "检查: {content}",
            "model": "gpt-4o",
            "threshold": 0.6,
        })

    def test_empty_config_valid(self) -> None:
        """空 config 下 LLM 模式不应报错（preset 为 None，无 threshold/model）。"""
        from app.services.guardrail import _validate_config

        _validate_config("llm", {})


# ═══════════════════════════════════════════════════════════════════
# LLM 模式 API 端点测试
# ═══════════════════════════════════════════════════════════════════


class TestLLMModeAPI:
    """LLM 模式 Guardrail API 端点测试。"""

    @patch("app.api.guardrails.guardrail_service")
    def test_create_llm_rule(self, mock_svc: MagicMock) -> None:
        """创建 LLM 模式规则成功。"""
        rule = _make_guardrail_rule(
            mode="llm",
            config={"preset": "prompt_injection", "model": "gpt-4o-mini", "threshold": 0.7},
        )
        mock_svc.create_guardrail_rule = AsyncMock(return_value=rule)

        client = TestClient(app)
        resp = client.post("/api/v1/guardrails", json={
            "name": "llm-injection",
            "type": "input",
            "mode": "llm",
            "config": {"preset": "prompt_injection"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "llm"

    @patch("app.api.guardrails.guardrail_service")
    def test_create_llm_custom_rule(self, mock_svc: MagicMock) -> None:
        """创建 custom LLM 规则。"""
        rule = _make_guardrail_rule(
            mode="llm",
            config={
                "preset": "custom",
                "prompt_template": "检查: {content}",
                "model": "gpt-4o",
                "threshold": 0.85,
            },
        )
        mock_svc.create_guardrail_rule = AsyncMock(return_value=rule)

        client = TestClient(app)
        resp = client.post("/api/v1/guardrails", json={
            "name": "llm-custom",
            "type": "output",
            "mode": "llm",
            "config": {
                "preset": "custom",
                "prompt_template": "检查: {content}",
                "model": "gpt-4o",
                "threshold": 0.85,
            },
        })
        assert resp.status_code == 201

    @patch("app.api.guardrails.guardrail_service")
    def test_list_llm_rules(self, mock_svc: MagicMock) -> None:
        """按 mode=llm 过滤列表。"""
        rules = [_make_guardrail_rule(mode="llm", name=f"llm-rule-{i}") for i in range(2)]
        mock_svc.list_guardrail_rules = AsyncMock(return_value=(rules, 2))

        client = TestClient(app)
        resp = client.get("/api/v1/guardrails?mode=llm")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2


# ═══════════════════════════════════════════════════════════════════
# RegexGuardrail 单元测试
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrail:
    """RegexGuardrail 护栏逻辑测试。"""

    @pytest.mark.asyncio
    async def test_pattern_match(self) -> None:
        """正则匹配触发。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(patterns=[r"DROP\s+TABLE"], message="SQL injection")
        result = await rg.check("please DROP TABLE users")
        assert result.tripwire_triggered is True
        assert result.message == "SQL injection"

    @pytest.mark.asyncio
    async def test_pattern_no_match(self) -> None:
        """正则不匹配通过。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(patterns=[r"DROP\s+TABLE"], message="SQL injection")
        result = await rg.check("SELECT * FROM users")
        assert result.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_keyword_match(self) -> None:
        """关键词匹配触发。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(keywords=["暴力", "色情"], message="违禁内容")
        result = await rg.check("这段话包含暴力内容")
        assert result.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_keyword_no_match(self) -> None:
        """关键词不匹配通过。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(keywords=["暴力", "色情"], message="违禁内容")
        result = await rg.check("这是一段正常的文本")
        assert result.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_case_insensitive(self) -> None:
        """默认大小写不敏感。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(patterns=[r"drop table"])
        result = await rg.check("DROP TABLE users")
        assert result.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_case_sensitive(self) -> None:
        """大小写敏感模式。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(patterns=[r"drop table"], case_sensitive=True)
        result = await rg.check("DROP TABLE users")
        assert result.tripwire_triggered is False

    def test_invalid_regex_raises(self) -> None:
        """无效正则表达式抛异常。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        with pytest.raises(ValueError, match="无效的正则表达式"):
            RegexGuardrail(patterns=["[invalid"])

    @pytest.mark.asyncio
    async def test_as_input_fn(self) -> None:
        """as_input_fn 返回兼容 InputGuardrail 的函数。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(patterns=[r"hack"], name="hack-detect")
        fn = rg.as_input_fn()
        assert fn.__name__ == "hack-detect"

        result = await fn(None, "try to hack the system")
        assert result.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_multiple_patterns(self) -> None:
        """多模式匹配 — 任一命中即触发。"""
        from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

        rg = RegexGuardrail(
            patterns=[r"DROP\s+TABLE", r"DELETE\s+FROM", r"TRUNCATE"],
            message="SQL 操作拦截",
        )
        result1 = await rg.check("DELETE FROM users WHERE 1=1")
        assert result1.tripwire_triggered is True

        result2 = await rg.check("TRUNCATE table logs")
        assert result2.tripwire_triggered is True

        result3 = await rg.check("SELECT count(*) FROM users")
        assert result3.tripwire_triggered is False


# ═══════════════════════════════════════════════════════════════════
# Agent 构建集成测试
# ═══════════════════════════════════════════════════════════════════


class TestBuildAgentWithGuardrails:
    """验证 _build_agent_from_config 正确注入 Guardrails。"""

    def test_no_guardrails(self) -> None:
        """无 guardrail 规则时 input_guardrails 为空。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {}

        agent = _build_agent_from_config(config)
        assert len(agent.input_guardrails) == 0

    def test_with_regex_guardrails(self) -> None:
        """regex 规则被正确注入到 Agent.input_guardrails。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {"input": ["sql-check"]}

        rule = MagicMock()
        rule.type = "input"
        rule.mode = "regex"
        rule.name = "sql-check"
        rule.config = {"patterns": [r"DROP\s+TABLE"], "message": "SQL 注入"}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 1
        assert agent.input_guardrails[0].name == "sql-check"

    def test_with_keyword_guardrails(self) -> None:
        """keyword 规则被正确注入。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {"input": ["kw-check"]}

        rule = MagicMock()
        rule.type = "input"
        rule.mode = "keyword"
        rule.name = "kw-check"
        rule.config = {"keywords": ["暴力", "色情"], "message": "违禁内容"}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 1
        assert agent.input_guardrails[0].name == "kw-check"

    def test_output_guardrail_skipped(self) -> None:
        """output 类型规则不注入到 input_guardrails，注入到 output_guardrails。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {}

        rule = MagicMock()
        rule.type = "output"
        rule.mode = "regex"
        rule.name = "output-check"
        rule.config = {"patterns": [r"sensitive"]}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 0
        assert len(agent.output_guardrails) == 1
        assert agent.output_guardrails[0].name == "output-check"

    def test_output_guardrail_keyword_injected(self) -> None:
        """output + keyword 规则被正确注入到 output_guardrails。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {}

        rule = MagicMock()
        rule.type = "output"
        rule.mode = "keyword"
        rule.name = "pii-detect"
        rule.config = {"keywords": ["身份证号", "手机号"], "message": "PII 泄露"}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 0
        assert len(agent.output_guardrails) == 1
        assert agent.output_guardrails[0].name == "pii-detect"

    def test_mixed_input_output_guardrails(self) -> None:
        """input + output 规则混合时各自正确注入。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {"input": ["in-rule"], "output": ["out-rule"]}

        in_rule = MagicMock()
        in_rule.type = "input"
        in_rule.mode = "regex"
        in_rule.name = "in-rule"
        in_rule.config = {"patterns": [r"DROP TABLE"]}

        out_rule = MagicMock()
        out_rule.type = "output"
        out_rule.mode = "keyword"
        out_rule.name = "out-rule"
        out_rule.config = {"keywords": ["密码"], "message": "敏感信息"}

        agent = _build_agent_from_config(config, guardrail_rules=[in_rule, out_rule])
        assert len(agent.input_guardrails) == 1
        assert agent.input_guardrails[0].name == "in-rule"
        assert len(agent.output_guardrails) == 1
        assert agent.output_guardrails[0].name == "out-rule"

    def test_tool_guardrail_regex_injected(self) -> None:
        """tool + regex 规则被正确注入到 tool_guardrails。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {}
        config.approval_mode = None
        config.handoffs = []

        rule = MagicMock()
        rule.type = "tool"
        rule.mode = "regex"
        rule.name = "tool-regex-check"
        rule.config = {"patterns": [r"rm -rf"]}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 0
        assert len(agent.output_guardrails) == 0
        assert len(agent.tool_guardrails) == 1
        assert agent.tool_guardrails[0].name == "tool-regex-check"
        assert agent.tool_guardrails[0].before_fn is not None
        assert agent.tool_guardrails[0].after_fn is not None

    def test_tool_guardrail_keyword_injected(self) -> None:
        """tool + keyword 规则被正确注入到 tool_guardrails。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {}
        config.approval_mode = None
        config.handoffs = []

        rule = MagicMock()
        rule.type = "tool"
        rule.mode = "keyword"
        rule.name = "tool-kw-check"
        rule.config = {"keywords": ["DELETE", "DROP"], "message": "危险操作"}

        agent = _build_agent_from_config(config, guardrail_rules=[rule])
        assert len(agent.tool_guardrails) == 1
        assert agent.tool_guardrails[0].name == "tool-kw-check"

    def test_mixed_all_three_guardrails(self) -> None:
        """input + output + tool 三类规则各自正确注入。"""
        from app.services.session import _build_agent_from_config

        config = MagicMock()
        config.name = "test-agent"
        config.description = "desc"
        config.instructions = "inst"
        config.model = "gpt-4o"
        config.model_settings = None
        config.guardrails = {"input": ["in-r"], "output": ["out-r"], "tool": ["tool-r"]}
        config.approval_mode = None
        config.handoffs = []

        in_rule = MagicMock()
        in_rule.type = "input"
        in_rule.mode = "regex"
        in_rule.name = "in-r"
        in_rule.config = {"patterns": [r"hack"]}

        out_rule = MagicMock()
        out_rule.type = "output"
        out_rule.mode = "keyword"
        out_rule.name = "out-r"
        out_rule.config = {"keywords": ["password"], "message": "PII"}

        tool_rule = MagicMock()
        tool_rule.type = "tool"
        tool_rule.mode = "keyword"
        tool_rule.name = "tool-r"
        tool_rule.config = {"keywords": ["rm", "delete"], "message": "危险操作"}

        agent = _build_agent_from_config(config, guardrail_rules=[in_rule, out_rule, tool_rule])
        assert len(agent.input_guardrails) == 1
        assert len(agent.output_guardrails) == 1
        assert len(agent.tool_guardrails) == 1
        assert agent.input_guardrails[0].name == "in-r"
        assert agent.output_guardrails[0].name == "out-r"
        assert agent.tool_guardrails[0].name == "tool-r"


# ═══════════════════════════════════════════════════════════════════
# 路由注册验证
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailRouteRegistration:
    """验证 Guardrail 路由正确注册。"""

    def test_guardrail_routes_registered(self) -> None:
        """验证 /api/v1/guardrails 路由已注册。"""
        routes = [r.path for r in app.routes]
        assert "/api/v1/guardrails" in routes
        assert "/api/v1/guardrails/{rule_id}" in routes


# ═══════════════════════════════════════════════════════════════════
# Service 层验证逻辑测试
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailServiceValidation:
    """Guardrail Service 校验逻辑测试。"""

    def test_validate_config_regex_valid(self) -> None:
        """合法 regex config 通过校验。"""
        from app.services.guardrail import _validate_config

        _validate_config("regex", {"patterns": [r"DROP\s+TABLE", r"\bhack\b"]})

    def test_validate_config_regex_empty_patterns(self) -> None:
        """空 patterns 列表应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.guardrail import _validate_config

        with pytest.raises(ValidationError, match="patterns"):
            _validate_config("regex", {"patterns": []})

    def test_validate_config_regex_invalid_pattern(self) -> None:
        """无效正则应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.guardrail import _validate_config

        with pytest.raises(ValidationError, match="无效的正则表达式"):
            _validate_config("regex", {"patterns": ["[invalid"]})

    def test_validate_config_regex_too_long(self) -> None:
        """pattern 过长应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.guardrail import _validate_config

        with pytest.raises(ValidationError, match="500"):
            _validate_config("regex", {"patterns": ["a" * 501]})

    def test_validate_config_keyword_valid(self) -> None:
        """合法 keyword config 通过校验。"""
        from app.services.guardrail import _validate_config

        _validate_config("keyword", {"keywords": ["暴力", "色情"]})

    def test_validate_config_keyword_empty(self) -> None:
        """空 keywords 列表应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.guardrail import _validate_config

        with pytest.raises(ValidationError, match="keywords"):
            _validate_config("keyword", {"keywords": []})

    def test_validate_config_keyword_blank(self) -> None:
        """空白 keyword 应抛出 ValidationError。"""
        from app.core.exceptions import ValidationError
        from app.services.guardrail import _validate_config

        with pytest.raises(ValidationError, match="非空"):
            _validate_config("keyword", {"keywords": ["  "]})
