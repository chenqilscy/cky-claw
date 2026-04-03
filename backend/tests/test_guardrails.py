"""Guardrail 规则 CRUD + RegexGuardrail 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "name": "test-rule",
        "description": "测试规则",
        "type": "input",
        "mode": "regex",
        "config": {"patterns": [r"DROP\s+TABLE"], "message": "SQL 注入检测"},
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
            GuardrailRuleCreate(name="test-rule", type="input", mode="llm")

    def test_rule_list_response(self) -> None:
        from app.schemas.guardrail import GuardrailRuleListResponse, GuardrailRuleResponse

        items = [GuardrailRuleResponse.model_validate(_make_guardrail_rule(name=f"rule-{i}")) for i in range(3)]
        resp = GuardrailRuleListResponse(items=items, total=10)
        assert len(resp.items) == 3
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
        assert data["items"] == []
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
        assert len(data["items"]) == 3

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
