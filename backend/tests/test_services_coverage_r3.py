"""Backend 覆盖率冲刺 Round 3 — 覆盖 session.py CRUD + helper 函数、
agent_locale 更多分支、guardrail 过滤、provider 解密失败、role 缺失分支、
deps 认证错误路径、_build_agent_from_config guardrail 分支等。

目标：将 backend 覆盖率从 93% → 95%+。
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError

# ── helpers ─────────────────────────────────────────────────────────────

def _scalar_one(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar_one.return_value = val
    return r


def _scalar(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar.return_value = val
    return r


def _scalar_one_or_none(val):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalar_one_or_none.return_value = val
    return r


def _scalars_all(vals: list):  # type: ignore[no-untyped-def]
    r = MagicMock()
    r.scalars.return_value.all.return_value = vals
    return r


def _make_orm(**fields) -> MagicMock:  # type: ignore[no-untyped-def]
    obj = MagicMock()
    for k, v in fields.items():
        setattr(obj, k, v)
    return obj


def _mock_db(*execute_results) -> AsyncMock:  # type: ignore[no-untyped-def]
    db = AsyncMock()
    if execute_results:
        db.execute = AsyncMock(side_effect=list(execute_results))
    else:
        db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.scalar = AsyncMock(return_value=None)
    return db


# ═════════════════════════════════════════════════════════════════════════
# Session Service — CRUD + Helper Functions
# ═════════════════════════════════════════════════════════════════════════


class TestSessionServiceR3:
    """覆盖 session.py create_session / get_session / list_sessions / get_session_messages。"""

    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        from app.schemas.session import SessionCreate
        from app.services.session import create_session

        mock_agent = _make_orm(id=uuid.uuid4(), name="agent1", is_active=True)
        db = _mock_db(
            _scalar_one_or_none(mock_agent),  # check agent exists
        )
        db.refresh = AsyncMock()
        data = SessionCreate(agent_name="agent1")
        await create_session(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_agent_not_found(self) -> None:
        from app.schemas.session import SessionCreate
        from app.services.session import create_session

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="不存在"):
            await create_session(db, SessionCreate(agent_name="nonexistent"))

    @pytest.mark.asyncio
    async def test_get_session(self) -> None:
        from app.services.session import get_session

        mock_s = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_s))
        result = await get_session(db, mock_s.id)
        assert result is mock_s

    @pytest.mark.asyncio
    async def test_get_session_not_found(self) -> None:
        from app.services.session import get_session

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_session(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_sessions_with_filters(self) -> None:
        from app.services.session import list_sessions

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_sessions(
            db, agent_name="agent1", status="active",
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_session_messages(self) -> None:
        from app.services.session import get_session_messages

        sid = uuid.uuid4()
        mock_s = _make_orm(id=sid, is_deleted=False)
        msg1 = _make_orm(id=1, role="user", content="hi")
        db = _mock_db(
            _scalar_one_or_none(mock_s),     # get_session 内部查询
            _scalars_all([msg1]),              # SessionMessage 查询
        )
        result = await get_session_messages(db, sid)
        assert len(result) == 1


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _build_output_type_from_schema
# ═════════════════════════════════════════════════════════════════════════


class TestBuildOutputType:
    """覆盖 _build_output_type_from_schema 各种 schema 类型分支。"""

    def test_basic_properties(self) -> None:
        from app.services.session import _build_output_type_from_schema

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "score": {"type": "number"},
                "active": {"type": "boolean"},
            },
            "required": ["name"],
        }
        model = _build_output_type_from_schema(schema, "test_agent")
        assert model is not None
        instance = model(name="test", age=25, score=9.5, active=True)
        assert instance.name == "test"

    def test_array_property(self) -> None:
        from app.services.session import _build_output_type_from_schema

        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        }
        model = _build_output_type_from_schema(schema, "tags_agent")
        assert model is not None

    def test_empty_properties_returns_none(self) -> None:
        from app.services.session import _build_output_type_from_schema

        # schema 带 properties 但空
        result = _build_output_type_from_schema({"properties": {}}, "empty")
        assert result is None

    def test_no_properties_returns_none(self) -> None:
        from app.services.session import _build_output_type_from_schema

        result = _build_output_type_from_schema({"type": "object"}, "no_props")
        assert result is None

    def test_optional_fields_with_default(self) -> None:
        from app.services.session import _build_output_type_from_schema

        schema = {
            "type": "object",
            "properties": {
                "color": {"type": "string", "default": "blue"},
            },
        }
        model = _build_output_type_from_schema(schema, "default_agent")
        assert model is not None
        instance = model()
        assert instance.color == "blue"


# ═════════════════════════════════════════════════════════════════════════
# Session Service — Token Usage Save Failure
# ═════════════════════════════════════════════════════════════════════════


class TestSessionTokenSaveFailure:
    """覆盖 _save_token_usage_from_trace 异常回滚路径。"""

    @pytest.mark.asyncio
    async def test_save_token_usage_no_trace(self) -> None:
        """trace=None → 立即返回。"""
        from app.services.session import _save_token_usage_from_trace

        db = _mock_db()
        await _save_token_usage_from_trace(db, None)
        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_token_usage_empty_spans(self) -> None:
        from app.services.session import _save_token_usage_from_trace

        mock_trace = MagicMock()
        mock_trace.spans = []
        db = _mock_db()
        await _save_token_usage_from_trace(db, mock_trace)
        db.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_token_usage_with_llm_span(self) -> None:
        from app.services.session import _save_token_usage_from_trace

        # span.type 是字符串 "llm"，span.token_usage 是 dict
        mock_span = MagicMock()
        mock_span.type = "llm"
        mock_span.name = "gpt-4o"
        mock_span.model = "gpt-4o"
        mock_span.span_id = str(uuid.uuid4())
        mock_span.parent_span_id = None
        mock_span.token_usage = {
            "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
        }
        mock_trace = MagicMock()
        mock_trace.trace_id = str(uuid.uuid4())
        mock_trace.spans = [mock_span]

        db = _mock_db()
        await _save_token_usage_from_trace(db, mock_trace, session_id=uuid.uuid4())
        db.add_all.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_token_usage_commit_failure_rollback(self) -> None:
        from app.services.session import _save_token_usage_from_trace

        mock_span = MagicMock()
        mock_span.type = "llm"
        mock_span.name = "gpt-4o"
        mock_span.model = "gpt-4o"
        mock_span.span_id = str(uuid.uuid4())
        mock_span.parent_span_id = None
        mock_span.token_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        mock_trace = MagicMock()
        mock_trace.trace_id = str(uuid.uuid4())
        mock_trace.spans = [mock_span]

        db = _mock_db()
        db.commit = AsyncMock(side_effect=Exception("db write error"))
        await _save_token_usage_from_trace(db, mock_trace)
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_token_usage_skip_non_llm_span(self) -> None:
        from app.services.session import _save_token_usage_from_trace

        mock_span = MagicMock()
        mock_span.type = "agent"  # 非 LLM
        mock_trace = MagicMock()
        mock_trace.spans = [mock_span]

        db = _mock_db()
        await _save_token_usage_from_trace(db, mock_trace)
        db.add_all.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _save_trace_from_processor
# ═════════════════════════════════════════════════════════════════════════


class TestSaveTraceFromProcessor:
    """覆盖 _save_trace_from_processor。"""

    @pytest.mark.asyncio
    async def test_save_trace_success(self) -> None:
        from app.services.session import _save_trace_from_processor

        mock_proc = MagicMock()
        mock_proc.get_collected_data.return_value = (
            {"id": str(uuid.uuid4()), "session_id": "sess-1"},
            [{"id": str(uuid.uuid4()), "trace_id": str(uuid.uuid4())}],
        )
        db = _mock_db()
        with patch("app.models.trace.TraceRecord", return_value=MagicMock()), \
             patch("app.models.trace.SpanRecord", return_value=MagicMock()):
            await _save_trace_from_processor(db, mock_proc)
        db.add.assert_called_once()
        db.add_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_trace_no_data(self) -> None:
        from app.services.session import _save_trace_from_processor

        mock_proc = MagicMock()
        mock_proc.get_collected_data.return_value = (None, [])
        db = _mock_db()
        await _save_trace_from_processor(db, mock_proc)
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_trace_exception_rollback(self) -> None:
        from app.services.session import _save_trace_from_processor

        mock_proc = MagicMock()
        mock_proc.get_collected_data.return_value = (
            {"id": str(uuid.uuid4())}, [],
        )
        db = _mock_db()
        with patch("app.models.trace.TraceRecord", side_effect=Exception("bad data")):
            await _save_trace_from_processor(db, mock_proc)
        db.rollback.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _ensure_model_prefix
# ═════════════════════════════════════════════════════════════════════════


class TestEnsureModelPrefix:
    """覆盖 session.py _ensure_model_prefix 的各分支。"""

    def test_empty_model(self) -> None:
        """model 为空字符串时原样返回。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("", "zhipu") == ""

    def test_none_model(self) -> None:
        """model 为 None 时原样返回。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix(None, "zhipu") is None

    def test_none_provider_type(self) -> None:
        """provider_type 为 None 时原样返回。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("glm-5", None) == "glm-5"

    def test_already_has_prefix(self) -> None:
        """模型名已包含 '/' 时跳过补全。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("openai/glm-5", "zhipu") == "openai/glm-5"

    def test_zhipu_prefix(self) -> None:
        """zhipu 厂商使用 openai/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("glm-5", "zhipu") == "openai/glm-5"

    def test_deepseek_prefix(self) -> None:
        """deepseek 厂商使用 deepseek/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("deepseek-chat", "deepseek") == "deepseek/deepseek-chat"

    def test_azure_prefix(self) -> None:
        """azure 厂商使用 azure/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("gpt-4o", "azure") == "azure/gpt-4o"

    def test_openai_no_prefix(self) -> None:
        """openai 原生厂商无前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("gpt-4o-mini", "openai") == "gpt-4o-mini"

    def test_anthropic_no_prefix(self) -> None:
        """anthropic 原生厂商无前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("claude-3-haiku", "anthropic") == "claude-3-haiku"

    def test_unknown_provider_type(self) -> None:
        """未知 provider_type 无前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("some-model", "google") == "some-model"

    def test_qwen_prefix(self) -> None:
        """qwen 厂商使用 openai/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("qwen-turbo", "qwen") == "openai/qwen-turbo"

    def test_moonshot_prefix(self) -> None:
        """moonshot 厂商使用 openai/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("moonshot-v1-8k", "moonshot") == "openai/moonshot-v1-8k"

    def test_minimax_prefix(self) -> None:
        """minimax 厂商使用 openai/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("MiniMax-Text-01", "minimax") == "openai/MiniMax-Text-01"

    def test_custom_no_prefix(self) -> None:
        """custom 厂商无前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("my-model", "custom") == "my-model"

    def test_doubao_prefix(self) -> None:
        """doubao 厂商使用 openai/ 前缀。"""
        from app.services.session import _ensure_model_prefix

        assert _ensure_model_prefix("doubao-lite", "doubao") == "openai/doubao-lite"


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _resolve_provider
# ═════════════════════════════════════════════════════════════════════════


class TestResolveProviderR3:
    """覆盖 session.py _resolve_provider 的各分支。"""

    @pytest.mark.asyncio
    async def test_no_provider_name(self) -> None:
        from app.services.session import _resolve_provider

        config = _make_orm(provider_name=None)
        db = _mock_db()
        result = await _resolve_provider(db, config)
        assert result == ({}, None)

    @pytest.mark.asyncio
    async def test_provider_not_found(self) -> None:
        from app.services.session import _resolve_provider

        config = _make_orm(provider_name="missing", name="agent1")
        db = _mock_db(_scalar_one_or_none(None))
        result = await _resolve_provider(db, config)
        assert result == ({}, None)

    @pytest.mark.asyncio
    async def test_provider_disabled(self) -> None:
        from app.services.session import _resolve_provider

        config = _make_orm(provider_name="disabled", name="agent1")
        mock_prov = _make_orm(
            is_enabled=False, name="disabled",
        )
        db = _mock_db(_scalar_one_or_none(mock_prov))
        with pytest.raises(NotFoundError, match="禁用"):
            await _resolve_provider(db, config)

    @pytest.mark.asyncio
    async def test_provider_api_key_decrypt_fail(self) -> None:
        from app.services.session import _resolve_provider

        config = _make_orm(provider_name="openai", name="agent1")
        mock_prov = _make_orm(
            is_enabled=True, name="openai",
            api_key_encrypted="bad_enc",
            base_url=None, auth_config=None,
            provider_type="openai",
        )
        db = _mock_db(_scalar_one_or_none(mock_prov))
        with patch("app.core.crypto.decrypt_api_key", side_effect=Exception("fail")), \
             pytest.raises(NotFoundError, match="解密失败"):
            await _resolve_provider(db, config)

    @pytest.mark.asyncio
    async def test_provider_auth_config_decrypt_fallback(self) -> None:
        from app.services.session import _resolve_provider

        config = _make_orm(provider_name="azure", name="agent1")
        mock_prov = _make_orm(
            is_enabled=True, name="azure",
            api_key_encrypted="enc_key",
            base_url="https://api.azure.com",
            auth_config={"api-version": "2024-01-01"},
            provider_type="azure",
        )
        db = _mock_db(_scalar_one_or_none(mock_prov))
        call_count = 0

        def selective_decrypt(v: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "decrypted_key"  # api_key
            raise Exception("fail")  # auth_config value 解密失败 → fallback

        with patch("app.core.crypto.decrypt_api_key", side_effect=selective_decrypt):
            result_kwargs, result_type = await _resolve_provider(db, config)
        assert result_kwargs["api_key"] == "decrypted_key"
        assert result_kwargs["api_base"] == "https://api.azure.com"
        assert "extra_headers" in result_kwargs
        assert result_type == "azure"


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _build_agent_from_config guardrail 分支
# ═════════════════════════════════════════════════════════════════════════


class TestBuildAgentFromConfig:
    """覆盖 _build_agent_from_config 中 guardrail 规则转换的各分支。"""

    def _config(self, **overrides) -> MagicMock:
        defaults = dict(
            name="test-agent", description="desc", instructions="do stuff",
            model="gpt-4o", model_settings=None, guardrails=None,
            approval_mode=None, output_type=None, handoffs=None,
            mcp_servers=None, agent_as_tools=None,
        )
        defaults.update(overrides)
        return _make_orm(**defaults)

    def test_no_guardrails(self) -> None:
        from app.services.session import _build_agent_from_config

        agent = _build_agent_from_config(self._config())
        assert agent.name == "test-agent"

    def test_regex_input_guardrail(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="no-ssn", type="input", mode="regex",
            config={"patterns": [r"\d{3}-\d{2}-\d{4}"], "message": "blocked"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 1

    def test_keyword_output_guardrail(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="no-bad", type="output", mode="keyword",
            config={"keywords": ["banned"], "message": "blocked"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.output_guardrails) == 1

    def test_regex_tool_guardrail(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="tool-guard", type="tool", mode="regex",
            config={"patterns": [".*"], "message": "match all"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.tool_guardrails) == 1

    def test_llm_prompt_injection_input(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="pi-guard", type="input", mode="llm",
            config={"preset": "prompt_injection", "threshold": 0.7, "model": "gpt-4o"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.input_guardrails) == 1

    def test_llm_content_safety_output(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="cs-guard", type="output", mode="llm",
            config={"preset": "content_safety", "threshold": 0.75, "model": "gpt-4o"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.output_guardrails) == 1

    def test_llm_custom_tool(self) -> None:
        from app.services.session import _build_agent_from_config

        rule = _make_orm(
            name="custom-guard", type="tool", mode="llm",
            config={"preset": "custom", "prompt_template": "Check: {content}",
                     "threshold": 0.8, "model": "gpt-4o"},
        )
        agent = _build_agent_from_config(self._config(), guardrail_rules=[rule])
        assert len(agent.tool_guardrails) == 1

    def test_approval_mode_suggest(self) -> None:
        from app.services.session import _build_agent_from_config

        agent = _build_agent_from_config(self._config(approval_mode="suggest"))
        assert agent.approval_mode is not None

    def test_output_type_from_schema(self) -> None:
        from app.services.session import _build_agent_from_config

        schema = {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        }
        agent = _build_agent_from_config(self._config(output_type=schema))
        assert agent.output_type is not None


# ═════════════════════════════════════════════════════════════════════════
# Session Service — _find_parent_agent_name
# ═════════════════════════════════════════════════════════════════════════


class TestFindParentAgentName:
    """覆盖 _find_parent_agent_name helper。"""

    def test_no_parent(self) -> None:
        from app.services.session import _find_parent_agent_name

        span = MagicMock(parent_span_id=None)
        result = _find_parent_agent_name([], span)
        assert result is None

    def test_parent_found(self) -> None:
        from app.services.session import _find_parent_agent_name

        parent = MagicMock(span_id="p1", type="agent")
        parent.name = "parent-agent"  # MagicMock.name 需要单独设置
        child = MagicMock(parent_span_id="p1")
        result = _find_parent_agent_name([parent], child)
        assert result == "parent-agent"

    def test_parent_not_found(self) -> None:
        from app.services.session import _find_parent_agent_name

        other = MagicMock(span_id="other", type="tool")
        child = MagicMock(parent_span_id="p1")
        result = _find_parent_agent_name([other], child)
        assert result is None


# ═════════════════════════════════════════════════════════════════════════
# Agent Locale — 更多分支
# ═════════════════════════════════════════════════════════════════════════


class TestAgentLocaleR3:
    """覆盖 agent_locale.py 更多分支。"""

    @pytest.mark.asyncio
    async def test_create_locale_with_default(self) -> None:
        """创建 is_default=True 的 locale 触发 _clear_default。"""
        from app.schemas.agent_locale import AgentLocaleCreate
        from app.services.agent_locale import create_locale

        aid = uuid.uuid4()
        db = _mock_db(
            _scalar_one_or_none(aid),       # _get_agent_id_by_name
            _scalar_one_or_none(None),       # exists check → no dup
            MagicMock(),                      # _clear_default (update stmt)
        )
        db.refresh = AsyncMock()
        data = AgentLocaleCreate(locale="zh", instructions="中文", is_default=True)
        await create_locale(db, "agent1", data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_locale(self) -> None:
        from app.schemas.agent_locale import AgentLocaleUpdate
        from app.services.agent_locale import update_locale

        aid = uuid.uuid4()
        mock_locale = _make_orm(
            id=uuid.uuid4(), locale="en", agent_id=aid,
            is_default=False, instructions="old",
        )
        db = _mock_db(
            _scalar_one_or_none(aid),         # _get_agent_id_by_name
            _scalar_one_or_none(mock_locale),  # _get_locale_record
        )
        data = AgentLocaleUpdate(instructions="new instructions")
        await update_locale(db, "agent1", "en", data)
        assert mock_locale.instructions == "new instructions"

    @pytest.mark.asyncio
    async def test_update_locale_set_default(self) -> None:
        """更新 is_default = True 时触发 _clear_default。"""
        from app.schemas.agent_locale import AgentLocaleUpdate
        from app.services.agent_locale import update_locale

        aid = uuid.uuid4()
        mock_locale = _make_orm(
            id=uuid.uuid4(), locale="en", agent_id=aid,
            is_default=False, instructions="old",
        )
        db = _mock_db(
            _scalar_one_or_none(aid),          # _get_agent_id_by_name
            _scalar_one_or_none(mock_locale),   # _get_locale_record
            MagicMock(),                         # _clear_default
        )
        data = AgentLocaleUpdate(instructions="updated", is_default=True)
        await update_locale(db, "agent1", "en", data)

    @pytest.mark.asyncio
    async def test_locale_not_found(self) -> None:
        from app.services.agent_locale import _get_locale_record

        aid = uuid.uuid4()
        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="不存在"):
            await _get_locale_record(db, aid, "xx")


# ═════════════════════════════════════════════════════════════════════════
# Guardrail — 过滤分支 + 更多校验
# ═════════════════════════════════════════════════════════════════════════


class TestGuardrailR3:
    """覆盖 guardrail.py 列表过滤分支和 LLM 模式校验。"""

    @pytest.mark.asyncio
    async def test_list_guardrail_rules_type_filter(self) -> None:
        from app.services.guardrail import list_guardrail_rules

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_guardrail_rules(db, type_filter="input")
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_guardrail_rules_mode_filter(self) -> None:
        from app.services.guardrail import list_guardrail_rules

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_guardrail_rules(db, mode_filter="regex")
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_guardrail_rules_enabled_only(self) -> None:
        from app.services.guardrail import list_guardrail_rules

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_guardrail_rules(db, enabled_only=True)
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_guardrail_rule_not_found(self) -> None:
        from app.services.guardrail import get_guardrail_rule

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_guardrail_rule(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_create_guardrail_llm_threshold_invalid(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="threshold"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="input", mode="llm",
                config={"preset": "prompt_injection", "threshold": 2.0},
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_regex_empty_patterns(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="patterns"):
            await create_guardrail_rule(
                db, name="g1", description="d",
                type_="input", mode="regex",
                config={},  # 缺少 patterns
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_keyword_empty(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="keywords"):
            await create_guardrail_rule(
                db, name="g2", description="d",
                type_="input", mode="keyword",
                config={},
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_invalid_type(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="type"):
            await create_guardrail_rule(
                db, name="g3", type_="bad_type",
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_invalid_mode(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="mode"):
            await create_guardrail_rule(
                db, name="g4", mode="bad_mode",
            )

    @pytest.mark.asyncio
    async def test_create_guardrail_llm_custom_missing_template(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db()
        with pytest.raises(ValidationError, match="prompt_template"):
            await create_guardrail_rule(
                db, name="g5", mode="llm",
                config={"preset": "custom"},
            )


# ═════════════════════════════════════════════════════════════════════════
# Provider — test_connection 解密失败分支
# ═════════════════════════════════════════════════════════════════════════


class TestProviderR3:
    """覆盖 provider.py test_connection 解密失败路径。"""

    @pytest.mark.asyncio
    async def test_connection_decrypt_fail(self) -> None:
        from app.services.provider import test_connection

        mock_prov = _make_orm(
            id=uuid.uuid4(), name="openai",
            provider_type="openai", base_url="https://api.openai.com/v1",
            api_key_encrypted="encrypted_key",
            is_active=True, auth_config=None, is_deleted=False,
            health_status="unknown", last_health_check=None,
        )
        db = _mock_db(_scalar_one_or_none(mock_prov))
        with patch("app.services.provider.decrypt_api_key", side_effect=Exception("decrypt error")):
            result = await test_connection(db, mock_prov.id)
        assert result["success"] is False
        assert "解密" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_auth_config_fallback(self) -> None:
        """auth_config 值解密失败时 fallback 到原值。"""
        from app.services.provider import test_connection

        mock_prov = _make_orm(
            id=uuid.uuid4(), name="azure",
            provider_type="azure", base_url="https://api.azure.com",
            api_key_encrypted="enc_key",
            is_active=True, is_deleted=False,
            auth_config={"api-version": "2024"},
            health_status="unknown", last_health_check=None,
        )
        db = _mock_db(_scalar_one_or_none(mock_prov))
        call_count = 0

        def selective_decrypt(v: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "decrypted_key"
            raise Exception("fail")

        with patch("app.services.provider.decrypt_api_key", side_effect=selective_decrypt), \
             patch("litellm.acompletion", new_callable=AsyncMock, return_value=MagicMock()):
            result = await test_connection(db, mock_prov.id)
        assert result["success"] is True


# ═════════════════════════════════════════════════════════════════════════
# Role — 缺失分支
# ═════════════════════════════════════════════════════════════════════════


class TestRoleServiceR3:
    """覆盖 role.py 的 create_role 冲突 + 更多 NotFound 分支。"""

    @pytest.mark.asyncio
    async def test_create_role_conflict(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.role import RoleCreate
        from app.services.role import create_role

        db = _mock_db()
        db.flush = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        data = RoleCreate(
            name="admin", description="Admin",
            permissions={"agents": ["read"]},
        )
        with pytest.raises(ConflictError):
            await create_role(db, data)

    @pytest.mark.asyncio
    async def test_update_role_not_found(self) -> None:
        from app.schemas.role import RoleUpdate
        from app.services.role import update_role

        db = _mock_db(_scalar_one_or_none(None))
        data = RoleUpdate(description="updated")
        with pytest.raises(NotFoundError, match="角色不存在"):
            await update_role(db, uuid.uuid4(), data)

    @pytest.mark.asyncio
    async def test_update_role_with_permissions(self) -> None:
        from app.schemas.role import RoleUpdate
        from app.services.role import update_role

        mock_role = _make_orm(
            id=uuid.uuid4(), is_system=False,
            description="old", permissions={"agents": ["read"]},
        )
        db = _mock_db(_scalar_one_or_none(mock_role))
        data = RoleUpdate(permissions={"agents": ["read", "write"]})
        result = await update_role(db, mock_role.id, data)
        assert result.permissions == {"agents": ["read", "write"]}

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self) -> None:
        from app.services.role import delete_role

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="角色不存在"):
            await delete_role(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_role_not_found(self) -> None:
        from app.services.role import get_role

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="角色不存在"):
            await get_role(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_seed_system_roles(self) -> None:
        from app.services.role import seed_system_roles

        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        await seed_system_roles(db)
        assert db.add.call_count >= 2
        db.commit.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════
# Deps — 认证错误路径
# ═════════════════════════════════════════════════════════════════════════


class TestDepsR3:
    """覆盖 core/deps.py 的 JWT 解码错误路径。"""

    def _creds(self, token: str = "dummy") -> MagicMock:
        c = MagicMock()
        c.credentials = token
        return c

    @pytest.mark.asyncio
    async def test_invalid_token(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import get_current_user

        db = _mock_db()
        with patch("app.core.deps.decode_access_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=self._creds(), db=db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_sub_in_token(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import get_current_user

        db = _mock_db()
        with patch("app.core.deps.decode_access_token", return_value={}):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=self._creds(), db=db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_uuid_sub(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import get_current_user

        db = _mock_db()
        with patch("app.core.deps.decode_access_token", return_value={"sub": "not-a-uuid"}):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=self._creds(), db=db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import get_current_user

        uid = str(uuid.uuid4())
        db = _mock_db(_scalar_one_or_none(None))
        with patch("app.core.deps.decode_access_token", return_value={"sub": uid}):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=self._creds(), db=db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from app.core.deps import get_current_user

        uid = uuid.uuid4()
        mock_user = _make_orm(id=uid, is_active=True, role="admin")
        db = _mock_db(_scalar_one_or_none(mock_user))
        with patch("app.core.deps.decode_access_token", return_value={"sub": str(uid)}):
            user = await get_current_user(credentials=self._creds(), db=db)
        assert user is mock_user

    @pytest.mark.asyncio
    async def test_require_admin_forbidden(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import require_admin

        mock_user = _make_orm(role="user")
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(user=mock_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_admin_success(self) -> None:
        from app.core.deps import require_admin

        mock_user = _make_orm(role="admin")
        result = await require_admin(user=mock_user)
        assert result is mock_user

    @pytest.mark.asyncio
    async def test_require_permission_role_has_perm(self) -> None:
        from app.core.deps import require_permission

        mock_role = _make_orm(permissions={"agents": ["read", "write"]})
        mock_user = _make_orm(role_id=uuid.uuid4(), role="user")
        db = _mock_db(_scalar_one_or_none(mock_role))

        check_fn = require_permission("agents", "write")
        result = await check_fn(user=mock_user, db=db)
        assert result is mock_user

    @pytest.mark.asyncio
    async def test_require_permission_role_missing_perm(self) -> None:
        from fastapi import HTTPException

        from app.core.deps import require_permission

        mock_role = _make_orm(
            name="viewer",
            permissions={"agents": ["read"]},
        )
        mock_user = _make_orm(role_id=uuid.uuid4(), role="user")
        db = _mock_db(_scalar_one_or_none(mock_role))

        check_fn = require_permission("agents", "write")
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(user=mock_user, db=db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_permission_fallback_admin(self) -> None:
        """无 role_id → fallback: admin 全通。"""
        from app.core.deps import require_permission

        mock_user = _make_orm(role_id=None, role="admin")
        db = _mock_db()
        check_fn = require_permission("agents", "write")
        result = await check_fn(user=mock_user, db=db)
        assert result is mock_user

    @pytest.mark.asyncio
    async def test_require_permission_fallback_read_only(self) -> None:
        """无 role_id + non-admin → read 允许, write 拒绝。"""
        from fastapi import HTTPException

        from app.core.deps import require_permission

        mock_user = _make_orm(role_id=None, role="user")
        db = _mock_db()

        # read 允许
        check_read = require_permission("agents", "read")
        result = await check_read(user=mock_user, db=db)
        assert result is mock_user

        # write 拒绝
        check_write = require_permission("agents", "write")
        with pytest.raises(HTTPException) as exc_info:
            await check_write(user=mock_user, db=db)
        assert exc_info.value.status_code == 403


# ═════════════════════════════════════════════════════════════════════════
# Scheduler Engine — get_run + start_scheduler
# ═════════════════════════════════════════════════════════════════════════


class TestSchedulerEngineR3:
    """覆盖 scheduler_engine.py 的 get_run / list_runs / start_scheduler。"""

    @pytest.mark.asyncio
    async def test_get_run(self) -> None:
        from app.services.scheduler_engine import get_run

        mock_run = _make_orm(id=uuid.uuid4())
        db = _mock_db(_scalar_one_or_none(mock_run))
        result = await get_run(db, mock_run.id)
        assert result is mock_run

    @pytest.mark.asyncio
    async def test_get_run_not_found(self) -> None:
        from app.services.scheduler_engine import get_run

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_run(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_runs(self) -> None:
        from app.services.scheduler_engine import list_runs

        db = _mock_db()
        db.scalar = AsyncMock(return_value=5)
        db.execute = AsyncMock(return_value=_scalars_all([_make_orm()]))
        rows, total = await list_runs(db, uuid.uuid4())
        assert total == 5

    def test_start_scheduler_duplicate(self) -> None:
        """调度器已在运行时跳过。"""
        import app.services.scheduler_engine as se

        # 模拟未完成的 task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        old_task = se._scheduler_task
        se._scheduler_task = mock_task
        try:
            se.start_scheduler()
            # 不应创建新 task
            assert se._scheduler_task is mock_task
        finally:
            se._scheduler_task = old_task


# ═════════════════════════════════════════════════════════════════════════
# IM Channel — 列表过滤 + 路由消息
# ═════════════════════════════════════════════════════════════════════════


class TestIMChannelR3:
    """覆盖 im_channel.py CRUD + route_message 分支。"""

    @pytest.mark.asyncio
    async def test_list_channels_with_filters(self) -> None:
        from app.services.im_channel import list_channels

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_channels(
            db, channel_type="wechat", is_enabled=True,
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_route_message_channel_not_found(self) -> None:
        from app.services.im_channel import route_message

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        result = await route_message(db, uuid.uuid4(), "user1", "hello")
        assert result["status"] == "error"
        assert "不存在" in result["message"]

    @pytest.mark.asyncio
    async def test_route_message_channel_disabled(self) -> None:
        from app.services.im_channel import route_message

        db = AsyncMock()
        ch = _make_orm(is_enabled=False, agent_id=uuid.uuid4())
        ch.name = "ch1"
        db.get = AsyncMock(return_value=ch)
        result = await route_message(db, uuid.uuid4(), "user1", "hello")
        assert result["status"] == "error"
        assert "禁用" in result["message"]

    @pytest.mark.asyncio
    async def test_route_message_no_agent(self) -> None:
        from app.services.im_channel import route_message

        db = AsyncMock()
        ch = _make_orm(is_enabled=True, agent_id=None)
        ch.name = "ch1"
        db.get = AsyncMock(return_value=ch)
        result = await route_message(db, uuid.uuid4(), "user1", "hello")
        assert result["status"] == "error"
        assert "Agent" in result["message"]

    @pytest.mark.asyncio
    async def test_route_message_success(self) -> None:
        from app.services.im_channel import route_message

        db = AsyncMock()
        ch = _make_orm(is_enabled=True, agent_id=uuid.uuid4())
        ch.name = "ch1"
        db.get = AsyncMock(return_value=ch)
        result = await route_message(db, uuid.uuid4(), "user1", "hello")
        assert result["status"] == "accepted"


# ═════════════════════════════════════════════════════════════════════════
# Tool Group — 列表过滤 + create + update
# ═════════════════════════════════════════════════════════════════════════


class TestToolGroupR3:
    """覆盖 tool_group.py list 过滤、create、update 分支。"""

    @pytest.mark.asyncio
    async def test_list_with_enabled_filter(self) -> None:
        from app.services.tool_group import list_tool_groups

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_tool_groups(db, is_enabled=True)
        assert total == 0

    @pytest.mark.asyncio
    async def test_create_tool_group(self) -> None:
        from app.schemas.tool_group import ToolDefinition, ToolGroupCreate
        from app.services.tool_group import create_tool_group

        db = _mock_db(_scalar_one_or_none(None))  # uniqueness check
        db.refresh = AsyncMock()
        data = ToolGroupCreate(
            name="my-tool-group",
            description="a group",
            tools=[ToolDefinition(name="t1", description="d1")],
        )
        await create_tool_group(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tool_group_tools_and_enabled(self) -> None:
        from app.schemas.tool_group import ToolDefinition, ToolGroupUpdate
        from app.services.tool_group import update_tool_group

        mock_tg = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            description="old", tools=[], is_enabled=True,
        )
        mock_tg.name = "my-group"
        db = _mock_db(_scalar_one_or_none(mock_tg))
        db.refresh = AsyncMock()
        data = ToolGroupUpdate(
            tools=[ToolDefinition(name="t2", description="d2")],
            is_enabled=False,
        )
        await update_tool_group(db, "my-group", data)
        assert mock_tg.is_enabled is False


# ═════════════════════════════════════════════════════════════════════════
# Approval — list 过滤 + resolve
# ═════════════════════════════════════════════════════════════════════════


class TestApprovalR3:
    """覆盖 approval.py list_approval_requests 过滤 + resolve_approval_request。"""

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self) -> None:
        from app.services.approval import list_approval_requests

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_approval_requests(db, status="pending")
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_invalid_status(self) -> None:
        from app.services.approval import list_approval_requests

        db = _mock_db()
        with pytest.raises(ValidationError, match="status"):
            await list_approval_requests(db, status="invalid_status")

    @pytest.mark.asyncio
    async def test_resolve_approve(self) -> None:
        from app.services.approval import resolve_approval_request

        mock_req = _make_orm(
            id=uuid.uuid4(), status="pending",
            agent_name="agent1", session_id=uuid.uuid4(),
        )
        db = _mock_db(_scalar_one_or_none(mock_req))
        with patch("app.services.approval.ApprovalManager") as MockMgr:
            MockMgr.get_instance.return_value.resolve.return_value = True
            result = await resolve_approval_request(db, mock_req.id, action="approve")
        assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_resolve_reject(self) -> None:
        from app.services.approval import resolve_approval_request

        mock_req = _make_orm(
            id=uuid.uuid4(), status="pending",
            agent_name="agent1", session_id=uuid.uuid4(),
        )
        db = _mock_db(_scalar_one_or_none(mock_req))
        with patch("app.services.approval.ApprovalManager") as MockMgr:
            MockMgr.get_instance.return_value.resolve.return_value = False
            result = await resolve_approval_request(db, mock_req.id, action="reject")
        assert result.status == "rejected"


# ═════════════════════════════════════════════════════════════════════════
# Guardrail — update + delete
# ═════════════════════════════════════════════════════════════════════════


class TestGuardrailUpdateDeleteR3:
    """覆盖 guardrail.py update/delete 分支。"""

    @pytest.mark.asyncio
    async def test_update_guardrail_type_and_mode(self) -> None:
        from app.services.guardrail import update_guardrail_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            type="input", mode="regex",
            config={"patterns": [".*"]}, is_enabled=True,
        )
        mock_rule.name = "rule1"
        db = _mock_db(_scalar_one_or_none(mock_rule))
        await update_guardrail_rule(
            db, mock_rule.id,
            type_="output", mode="keyword",
            config={"keywords": ["banned"]},
        )
        assert mock_rule.type == "output"
        assert mock_rule.mode == "keyword"

    @pytest.mark.asyncio
    async def test_update_guardrail_invalid_type(self) -> None:
        from app.services.guardrail import update_guardrail_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            type="input", mode="regex",
        )
        mock_rule.name = "rule1"
        db = _mock_db(_scalar_one_or_none(mock_rule))
        with pytest.raises(ValidationError, match="type"):
            await update_guardrail_rule(db, mock_rule.id, type_="bad")

    @pytest.mark.asyncio
    async def test_update_guardrail_invalid_mode(self) -> None:
        from app.services.guardrail import update_guardrail_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            type="input", mode="regex",
        )
        mock_rule.name = "rule1"
        db = _mock_db(_scalar_one_or_none(mock_rule))
        with pytest.raises(ValidationError, match="mode"):
            await update_guardrail_rule(db, mock_rule.id, mode="bad")

    @pytest.mark.asyncio
    async def test_delete_guardrail_rule(self) -> None:
        from app.services.guardrail import delete_guardrail_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            is_enabled=True,
        )
        mock_rule.name = "rule1"
        db = _mock_db(_scalar_one_or_none(mock_rule))
        await delete_guardrail_rule(db, mock_rule.id)
        assert mock_rule.is_deleted is True


# ═════════════════════════════════════════════════════════════════════════
# Session — delete_session
# ═════════════════════════════════════════════════════════════════════════


class TestSessionDeleteR3:
    """覆盖 session.py delete_session。"""

    @pytest.mark.asyncio
    async def test_delete_session(self) -> None:
        from app.services.session import delete_session

        mock_s = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_s))
        await delete_session(db, mock_s.id)
        assert mock_s.is_deleted is True


# ═════════════════════════════════════════════════════════════════════════
# Session — _resolve_mcp_tools (stack=None 路径 + connectivity 路径)
# ═════════════════════════════════════════════════════════════════════════


class TestResolveMCPToolsR3:
    """覆盖 _resolve_mcp_tools 各分支。"""

    @pytest.mark.asyncio
    async def test_no_mcp_servers(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = _make_orm(mcp_servers=[])
        db = _mock_db()
        result = await _resolve_mcp_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_stack_none_logs_only(self) -> None:
        """stack=None 时仅日志，不实际连接。"""
        from app.services.session import _resolve_mcp_tools

        config = _make_orm(mcp_servers=["mcp1"])
        config.name = "agent1"
        mock_mcp_config = _make_orm(name="mcp1")
        db = _mock_db()
        with patch("app.services.mcp_server.get_mcp_servers_by_names", new_callable=AsyncMock, return_value=[mock_mcp_config]):
            result = await _resolve_mcp_tools(db, config, stack=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_mcp_server_logged(self) -> None:
        from app.services.session import _resolve_mcp_tools

        config = _make_orm(mcp_servers=["mcp-missing"])
        config.name = "agent1"
        db = _mock_db()
        with patch("app.services.mcp_server.get_mcp_servers_by_names", new_callable=AsyncMock, return_value=[]):
            result = await _resolve_mcp_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_mcp_connect_import_error(self) -> None:
        """MCP SDK 未安装时 ImportError 被捕获。"""
        from app.services.session import _resolve_mcp_tools

        config = _make_orm(mcp_servers=["mcp1"])
        config.name = "agent1"
        mock_mcp_config = _make_orm(
            name="mcp1", transport_type="stdio",
            command="mcp-server", url=None,
            auth_config=None, env=None,
        )
        mock_stack = AsyncMock()

        db = _mock_db()
        with patch("app.services.mcp_server.get_mcp_servers_by_names", new_callable=AsyncMock, return_value=[mock_mcp_config]), \
             patch("ckyclaw_framework.mcp.connection.connect_and_discover", side_effect=ImportError("no mcp")):
            result = await _resolve_mcp_tools(db, config, stack=mock_stack)
        assert result == []

    @pytest.mark.asyncio
    async def test_mcp_connect_auth_config_decrypt(self) -> None:
        """auth_config 解密 + 连接异常被捕获。"""
        from app.services.session import _resolve_mcp_tools

        config = _make_orm(mcp_servers=["mcp1"])
        config.name = "agent1"
        mock_mcp_config = _make_orm(
            name="mcp1", transport_type="sse",
            command=None, url="http://mcp:8080",
            auth_config={"Authorization": "enc_token"},
            env={"KEY": "val"},
        )
        mock_stack = AsyncMock()

        db = _mock_db()
        with patch("app.services.mcp_server.get_mcp_servers_by_names", new_callable=AsyncMock, return_value=[mock_mcp_config]), \
             patch("app.core.crypto.decrypt_api_key", return_value="decrypted_token"), \
             patch("ckyclaw_framework.mcp.connection.connect_and_discover", side_effect=Exception("connect fail")):
            result = await _resolve_mcp_tools(db, config, stack=mock_stack)
        assert result == []


# ═════════════════════════════════════════════════════════════════════════
# Session — _resolve_handoff_agents / _resolve_agent_tools (循环引用检测)
# ═════════════════════════════════════════════════════════════════════════


class TestResolveHandoffR3:
    """覆盖 _resolve_handoff_agents 循环引用和深度限制。"""

    @pytest.mark.asyncio
    async def test_no_handoffs(self) -> None:
        from app.services.session import _resolve_handoff_agents

        config = _make_orm(handoffs=[])
        db = _mock_db()
        result = await _resolve_handoff_agents(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_cycle_detection(self) -> None:
        from app.services.session import _resolve_handoff_agents

        config = _make_orm(handoffs=["agent2"])
        config.name = "agent1"
        db = _mock_db()
        # agent2 已在 visited 中 → 循环检测
        result = await _resolve_handoff_agents(db, config, visited={"agent1", "agent2"})
        assert result == []

    @pytest.mark.asyncio
    async def test_depth_limit(self) -> None:
        from app.services.session import _resolve_handoff_agents

        config = _make_orm(handoffs=["deepagent"])
        config.name = "agent1"
        db = _mock_db()
        result = await _resolve_handoff_agents(db, config, depth=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_target_not_found(self) -> None:
        from app.services.session import _resolve_handoff_agents

        config = _make_orm(handoffs=["missing-agent"])
        config.name = "agent1"
        db = _mock_db(_scalars_all([]))  # no target found
        result = await _resolve_handoff_agents(db, config)
        assert result == []


class TestResolveAgentToolsR3:
    """覆盖 _resolve_agent_tools 循环引用和深度限制。"""

    @pytest.mark.asyncio
    async def test_no_agent_tools(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = _make_orm(agent_tools=[])
        db = _mock_db()
        result = await _resolve_agent_tools(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_cycle_detection(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = _make_orm(agent_tools=["tool-agent"])
        config.name = "agent1"
        db = _mock_db()
        result = await _resolve_agent_tools(db, config, visited={"agent1", "tool-agent"})
        assert result == []

    @pytest.mark.asyncio
    async def test_depth_limit(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = _make_orm(agent_tools=["deepagent"])
        config.name = "agent1"
        db = _mock_db()
        result = await _resolve_agent_tools(db, config, depth=3)
        assert result == []

    @pytest.mark.asyncio
    async def test_target_not_found(self) -> None:
        from app.services.session import _resolve_agent_tools

        config = _make_orm(agent_tools=["missing-tool-agent"])
        config.name = "agent1"
        db = _mock_db(_scalars_all([]))
        result = await _resolve_agent_tools(db, config)
        assert result == []


# ═════════════════════════════════════════════════════════════════════════
# Session — _resolve_tool_groups
# ═════════════════════════════════════════════════════════════════════════


class TestResolveToolGroupsR3:
    """覆盖 _resolve_tool_groups 分支。"""

    @pytest.mark.asyncio
    async def test_no_tool_groups(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = _make_orm(tool_groups=[])
        db = _mock_db()
        result = await _resolve_tool_groups(db, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_tool_group_with_tools(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = _make_orm(tool_groups=["grp1"])
        config.name = "agent1"
        mock_tg = _make_orm(
            tools=[
                {"name": "t1", "description": "desc1", "parameters_schema": {"type": "object", "properties": {}}},
                {"name": "t2", "description": "desc2"},
            ],
        )
        mock_tg.name = "grp1"
        db = _mock_db(_scalars_all([mock_tg]))
        result = await _resolve_tool_groups(db, config)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_tool_group_missing_warns(self) -> None:
        from app.services.session import _resolve_tool_groups

        config = _make_orm(tool_groups=["missing-grp"])
        config.name = "agent1"
        db = _mock_db(_scalars_all([]))
        result = await _resolve_tool_groups(db, config)
        assert result == []


# ═════════════════════════════════════════════════════════════════════════
# Agent — get_agent_by_name NotFound / create IntegrityError / update guardrails+metadata
# ═════════════════════════════════════════════════════════════════════════


class TestAgentServiceR3:
    """覆盖 agent.py 缺失分支：L62 get_agent_by_name NotFound、
    L91-93 create_agent IntegrityError、L125/L127 update guardrails+metadata。"""

    @pytest.mark.asyncio
    async def test_get_agent_by_name_not_found(self) -> None:
        from app.services.agent import get_agent_by_name

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="不存在"):
            await get_agent_by_name(db, "no-such-agent")

    @pytest.mark.asyncio
    async def test_create_agent_integrity_error(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.agent import AgentCreate
        from app.services.agent import create_agent

        data = AgentCreate(name="dup-agent", instructions="x")
        db = _mock_db(_scalar_one_or_none(None))  # 前置检查无冲突
        db.flush = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
        with pytest.raises(ConflictError, match="已存在"):
            await create_agent(db, data)

    @pytest.mark.asyncio
    async def test_update_agent_guardrails_and_metadata(self) -> None:
        from app.schemas.agent import AgentUpdate, GuardrailsConfig
        from app.services.agent import update_agent

        mock_agent = _make_orm(
            id=uuid.uuid4(), is_active=True, is_deleted=False,
            description="d", instructions="i", model="gpt-4",
            model_settings=None, tool_groups=[], handoffs=[],
            guardrails={}, approval_mode=None, mcp_servers=[],
            skills=[], output_type=None, metadata_={},
        )
        mock_agent.name = "test-agent"
        db = _mock_db(
            _scalar_one_or_none(mock_agent),  # get_agent_by_name
            MagicMock(),                      # create_version (execute)
        )
        gc = GuardrailsConfig(input=["rule1"], output=[], tool=[])
        data = AgentUpdate(guardrails=gc, metadata={"key": "val"})
        with patch("app.services.agent.create_version", new_callable=AsyncMock):
            await update_agent(db, "test-agent", data)
        assert mock_agent.metadata_ == {"key": "val"}
        assert mock_agent.guardrails == gc.model_dump()


# ═════════════════════════════════════════════════════════════════════════
# Team — update 校验分支
# ═════════════════════════════════════════════════════════════════════════


class TestTeamUpdateR3:
    """覆盖 team.py update_team 校验：无效 protocol、COORDINATOR 缺 coordinator、IntegrityError。"""

    @pytest.mark.asyncio
    async def test_update_invalid_protocol(self) -> None:
        from app.schemas.team import TeamConfigUpdate
        from app.services.team import update_team

        mock_team = _make_orm(
            id=uuid.uuid4(), is_deleted=False, protocol="SEQUENTIAL",
            coordinator_agent_id=None,
        )
        mock_team.name = "team1"
        db = _mock_db(_scalar_one_or_none(mock_team))
        data = TeamConfigUpdate(protocol="INVALID")
        with pytest.raises(ValueError, match="无效协议"):
            await update_team(db, mock_team.id, data)

    @pytest.mark.asyncio
    async def test_update_coordinator_missing_agent_id(self) -> None:
        from app.schemas.team import TeamConfigUpdate
        from app.services.team import update_team

        mock_team = _make_orm(
            id=uuid.uuid4(), is_deleted=False, protocol="SEQUENTIAL",
            coordinator_agent_id=None,
        )
        mock_team.name = "team1"
        db = _mock_db(_scalar_one_or_none(mock_team))
        data = TeamConfigUpdate(protocol="COORDINATOR")
        with pytest.raises(ValueError, match="COORDINATOR"):
            await update_team(db, mock_team.id, data)

    @pytest.mark.asyncio
    async def test_update_integrity_error(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.team import TeamConfigUpdate
        from app.services.team import update_team

        mock_team = _make_orm(
            id=uuid.uuid4(), is_deleted=False, protocol="SEQUENTIAL",
            coordinator_agent_id=None,
        )
        mock_team.name = "team1"
        db = _mock_db(_scalar_one_or_none(mock_team))
        db.commit = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
        data = TeamConfigUpdate(name="dup-name")
        with pytest.raises(ConflictError, match="已存在"):
            await update_team(db, mock_team.id, data)


# ═════════════════════════════════════════════════════════════════════════
# Alert — org_id 过滤 / update / invalid operator
# ═════════════════════════════════════════════════════════════════════════


class TestAlertServiceR3:
    """覆盖 alert.py L52 org_id、L102-107 update、L236 invalid operator。"""

    @pytest.mark.asyncio
    async def test_list_with_org_id_filter(self) -> None:
        from app.services.alert import list_alert_rules

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_alert_rules(db, org_id=uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_alert_rule(self) -> None:
        from app.schemas.alert import AlertRuleUpdate
        from app.services.alert import update_alert_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            name="r1", severity="warning",
        )
        mock_rule.name = "r1"
        db = _mock_db()
        data = AlertRuleUpdate(severity="critical", is_enabled=False)
        result = await update_alert_rule(db, mock_rule, data)
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_evaluate_rule_invalid_operator(self) -> None:
        from app.services.alert import evaluate_rule

        mock_rule = _make_orm(
            id=uuid.uuid4(), metric="token_usage_total",
            operator="INVALID_OP", threshold=100.0,
            window_minutes=60, agent_name=None,
            last_triggered_at=None, cooldown_minutes=0,
        )
        mock_rule.name = "r1"
        db = _mock_db(_scalar(50.0))  # _compute_metric result
        result = await evaluate_rule(db, mock_rule, auto_commit=False)
        assert result is None


# ═════════════════════════════════════════════════════════════════════════
# Skill — NotFound / org_id / update category+metadata / search category
# ═════════════════════════════════════════════════════════════════════════


class TestSkillServiceR3:
    """覆盖 skill.py 缺失分支。"""

    @pytest.mark.asyncio
    async def test_get_skill_by_name_not_found(self) -> None:
        from app.services.skill import get_skill_by_name

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="不存在"):
            await get_skill_by_name(db, "no-skill")

    @pytest.mark.asyncio
    async def test_list_skills_with_org_id(self) -> None:
        from app.services.skill import list_skills

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_skills(db, org_id=uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_skill_category_and_metadata(self) -> None:
        from app.schemas.skill import SkillCategoryEnum, SkillUpdate
        from app.services.skill import update_skill

        mock_skill = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            category="custom", metadata_={},
        )
        mock_skill.name = "skill1"
        db = _mock_db(_scalar_one_or_none(mock_skill))
        data = SkillUpdate(category=SkillCategoryEnum.PUBLIC, metadata={"env": "prod"})
        result = await update_skill(db, mock_skill.id, data)
        assert result.category == "public"
        assert result.metadata_ == {"env": "prod"}

    @pytest.mark.asyncio
    async def test_search_skills_with_category(self) -> None:
        from app.schemas.skill import SkillCategoryEnum, SkillSearchRequest
        from app.services.skill import search_skills

        db = _mock_db(_scalars_all([]))
        req = SkillSearchRequest(query="test", category=SkillCategoryEnum.PUBLIC)
        result = await search_skills(db, req)
        assert result == []


# ═════════════════════════════════════════════════════════════════════════
# Approval — agent_name + session_id 过滤
# ═════════════════════════════════════════════════════════════════════════


class TestApprovalFilterR3:
    """覆盖 approval.py L40-44 agent_name / session_id 过滤。"""

    @pytest.mark.asyncio
    async def test_list_with_agent_name(self) -> None:
        from app.services.approval import list_approval_requests

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_approval_requests(db, agent_name="my-agent")
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_session_id(self) -> None:
        from app.services.approval import list_approval_requests

        db = _mock_db(_scalar(0), _scalars_all([]))
        rows, total = await list_approval_requests(db, session_id=uuid.uuid4())
        assert total == 0


# ═════════════════════════════════════════════════════════════════════════
# AgentLocale — is_default=False 分支 + _has_other_default
# ═════════════════════════════════════════════════════════════════════════


class TestAgentLocaleDefaultR3:
    """覆盖 agent_locale.py L86-91 is_default 切换 + L138-143 _has_other_default。"""

    @pytest.mark.asyncio
    async def test_unset_default_with_other_existing(self) -> None:
        """设 is_default=False，当前记录是默认，但有其他默认 → 正常取消。"""
        from app.schemas.agent_locale import AgentLocaleUpdate
        from app.services.agent_locale import update_locale

        aid = uuid.uuid4()
        record_id = uuid.uuid4()
        mock_locale = _make_orm(
            id=record_id, locale="en", agent_id=aid,
            is_default=True, instructions="old",
        )
        db = _mock_db(
            _scalar_one_or_none(aid),           # _get_agent_id_by_name
            _scalar_one_or_none(mock_locale),    # _get_locale_record
            _scalar_one_or_none(uuid.uuid4()),   # _has_other_default → True
        )
        data = AgentLocaleUpdate(instructions="upd", is_default=False)
        result = await update_locale(db, "agent1", "en", data)
        assert result.is_default is False

    @pytest.mark.asyncio
    async def test_unset_default_no_other_raises(self) -> None:
        """设 is_default=False，当前是唯一默认 → ValidationError。"""
        from app.schemas.agent_locale import AgentLocaleUpdate
        from app.services.agent_locale import update_locale

        aid = uuid.uuid4()
        record_id = uuid.uuid4()
        mock_locale = _make_orm(
            id=record_id, locale="en", agent_id=aid,
            is_default=True, instructions="old",
        )
        db = _mock_db(
            _scalar_one_or_none(aid),           # _get_agent_id_by_name
            _scalar_one_or_none(mock_locale),    # _get_locale_record
            _scalar_one_or_none(None),           # _has_other_default → False
        )
        data = AgentLocaleUpdate(instructions="upd", is_default=False)
        with pytest.raises(ValidationError, match="唯一"):
            await update_locale(db, "agent1", "en", data)


# ═════════════════════════════════════════════════════════════════════════
# Scheduler Engine — start_scheduler 新任务创建
# ═════════════════════════════════════════════════════════════════════════


class TestSchedulerStartR3:
    """覆盖 scheduler_engine.py start_scheduler 创建任务分支 (L168-169)。"""

    @pytest.mark.asyncio
    async def test_start_scheduler_creates_task(self) -> None:
        import app.services.scheduler_engine as se

        # 确保没有已有 task
        old_task = getattr(se, "_scheduler_task", None)
        se._scheduler_task = None  # type: ignore[attr-defined]
        try:
            with patch.object(se, "_scheduler_loop", new_callable=AsyncMock):
                se.start_scheduler()
            task = se._scheduler_task  # type: ignore[attr-defined]
            assert task is not None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            se._scheduler_task = old_task  # type: ignore[attr-defined]
