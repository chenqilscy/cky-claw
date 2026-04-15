"""Service 层覆盖率冲刺测试 — 批量覆盖 CRUD + 业务逻辑服务函数。

目标：将 backend 覆盖率从 76% 大幅提升。
覆盖范围：auth, trace, provider, provider_model, mcp_server, rate_limiter,
agent_locale, agent_template, agent_version, skill, memory, token_usage,
im_channel, supervision, evaluation, apm, config_change, scheduled_task,
role, guardrail, approval, workflow, alert, tool_group, agent, pagination 等。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError

# ── helpers ──────────────────────────────────────────────────────────────

def _scalar_one(val):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.scalar_one() → val。"""
    r = MagicMock()
    r.scalar_one.return_value = val
    return r


def _scalar(val):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.scalar() → val。"""
    r = MagicMock()
    r.scalar.return_value = val
    return r


def _scalar_one_or_none(val):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.scalar_one_or_none() → val。"""
    r = MagicMock()
    r.scalar_one_or_none.return_value = val
    return r


def _scalars_all(vals: list):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.scalars().all() → vals。"""
    r = MagicMock()
    r.scalars.return_value.all.return_value = vals
    return r


def _rows(vals: list):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.all() → vals。"""
    r = MagicMock()
    r.all.return_value = vals
    return r


def _one(val):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.one() → val。"""
    r = MagicMock()
    r.one.return_value = val
    return r


def _rowcount(n: int):  # type: ignore[no-untyped-def]
    """构造 db.execute() 返回：.rowcount → n。"""
    r = MagicMock()
    r.rowcount = n
    return r


def _mock_db(*execute_results) -> AsyncMock:  # type: ignore[no-untyped-def]
    """创建 mock AsyncSession，execute 按顺序返回结果。"""
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


def _make_orm(**fields) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造 mock ORM 对象。"""
    obj = MagicMock()
    for k, v in fields.items():
        setattr(obj, k, v)
    return obj


# ── Pagination Schema ────────────────────────────────────────────────────


class TestPaginationSchema:
    """覆盖 schemas/pagination.py (0% → 100%)。"""

    def test_defaults(self) -> None:
        from app.schemas.pagination import PaginatedResponse
        resp = PaginatedResponse[str]()
        assert resp.data == []
        assert resp.total == 0
        assert resp.limit == 20
        assert resp.offset == 0

    def test_with_data(self) -> None:
        from app.schemas.pagination import PaginatedResponse
        resp = PaginatedResponse[str](data=["a", "b"], total=10, limit=5, offset=5)
        assert len(resp.data) == 2
        assert resp.total == 10


# ── Auth Service ─────────────────────────────────────────────────────────


class TestAuthService:
    """覆盖 services/auth.py 未覆盖行。"""

    @pytest.mark.asyncio
    async def test_register_user(self) -> None:
        from app.schemas.auth import UserRegister
        from app.services.auth import register_user

        db = _mock_db()
        data = UserRegister(username="bob", email="bob@test.com", password="secret123")
        with patch("app.services.auth.hash_password", return_value="hashed_pw"):
            await register_user(db, data)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_conflict(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.schemas.auth import UserRegister
        from app.services.auth import register_user

        db = _mock_db()
        db.flush = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        data = UserRegister(username="bob", email="bob@test.com", password="secret123")
        with patch("app.services.auth.hash_password", return_value="hashed_pw"), pytest.raises(ConflictError):
            await register_user(db, data)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self) -> None:
        from app.services.auth import authenticate_user

        mock_user = _make_orm(
            id=uuid.uuid4(), username="bob",
            hashed_password="$2b$12$test", role="user", is_active=True,
        )
        db = _mock_db(_scalar_one_or_none(mock_user))
        with patch("app.services.auth.verify_password", return_value=True), \
             patch("app.services.auth.create_access_token", return_value="tok123"), \
             patch("app.services.auth.create_refresh_token", return_value="ref456"):
            access_token, refresh_token = await authenticate_user(db, "bob", "secret")
        assert access_token == "tok123"
        assert refresh_token == "ref456"

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self) -> None:
        from app.services.auth import authenticate_user

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(AuthenticationError):
            await authenticate_user(db, "nobody", "pass")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self) -> None:
        from app.services.auth import authenticate_user

        mock_user = _make_orm(
            id=uuid.uuid4(), username="bob",
            hashed_password="$2b$12$test", role="user",
        )
        db = _mock_db(_scalar_one_or_none(mock_user))
        with patch("app.services.auth.verify_password", return_value=False), pytest.raises(AuthenticationError):
            await authenticate_user(db, "bob", "wrong")

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self) -> None:
        from app.services.auth import get_user_by_id

        uid = uuid.uuid4()
        mock_user = _make_orm(id=uid, username="bob")
        db = _mock_db(_scalar_one_or_none(mock_user))
        user = await get_user_by_id(db, str(uid))
        assert user is mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_id_invalid_uuid(self) -> None:
        from app.services.auth import get_user_by_id

        db = _mock_db()
        with pytest.raises(NotFoundError):
            await get_user_by_id(db, "not-a-uuid")

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self) -> None:
        from app.services.auth import get_user_by_id

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_user_by_id(db, str(uuid.uuid4()))


# ── Trace Service ────────────────────────────────────────────────────────


class TestTraceService:
    """覆盖 services/trace.py 未覆盖函数 (12% → high%)。"""

    @pytest.mark.asyncio
    async def test_list_traces_basic(self) -> None:
        from app.services.trace import list_traces

        mock_trace = _make_orm(id="t1")
        db = _mock_db(_scalar_one(1), _scalars_all([mock_trace]))
        rows, total = await list_traces(db)
        assert total == 1
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_list_traces_with_filters(self) -> None:
        from app.services.trace import list_traces

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_traces(
            db,
            session_id=uuid.uuid4(),
            agent_name="a",
            workflow_name="w",
            status="completed",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            min_duration_ms=100,
            max_duration_ms=5000,
            has_guardrail_triggered=True,
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_spans_basic(self) -> None:
        from app.services.trace import list_spans

        db = _mock_db(_scalar_one(2), _scalars_all([_make_orm(), _make_orm()]))
        rows, total = await list_spans(db)
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_spans_with_filters(self) -> None:
        from app.services.trace import list_spans

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_spans(
            db,
            trace_id="t1",
            type="llm",
            status="completed",
            name="test",
            min_duration_ms=50,
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_trace_stats(self) -> None:
        from app.services.trace import get_trace_stats

        trace_row = MagicMock()
        trace_row.total_traces = 10
        trace_row.avg_duration_ms = 150.5
        trace_row.error_count = 2
        type_row1 = MagicMock(type="llm", cnt=5)
        type_row2 = MagicMock(type="guardrail", cnt=3)
        token_row1 = MagicMock(token_usage={"prompt_tokens": 100, "completion_tokens": 50})
        token_row2 = MagicMock(token_usage={"prompt_tokens": 200, "completion_tokens": 80})
        db = _mock_db(
            _one(trace_row),
            _scalar_one(8),
            _rows([type_row1, type_row2]),
            _rows([token_row1, token_row2]),
            _scalar_one(1),
        )
        result = await get_trace_stats(
            db,
            session_id=uuid.uuid4(),
            agent_name="a",
            end_time=datetime.now(UTC),
        )
        assert result["total_traces"] == 10
        assert result["total_tokens"]["prompt_tokens"] == 300
        assert result["total_tokens"]["completion_tokens"] == 130
        assert result["guardrail_stats"]["triggered"] == 1

    @pytest.mark.asyncio
    async def test_get_trace_stats_empty(self) -> None:
        from app.services.trace import get_trace_stats

        trace_row = MagicMock()
        trace_row.total_traces = 0
        trace_row.avg_duration_ms = None
        trace_row.error_count = 0
        db = _mock_db(
            _one(trace_row),
            _scalar_one(0),
            _rows([]),
            _rows([]),
            _scalar_one(0),
        )
        result = await get_trace_stats(db)
        assert result["total_traces"] == 0
        assert result["error_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_trace_detail_success(self) -> None:
        from app.services.trace import get_trace_detail

        mock_trace = _make_orm(id="t1")
        mock_span = _make_orm(id="s1")
        db = _mock_db(
            _scalar_one_or_none(mock_trace),
            _scalars_all([mock_span]),
        )
        trace, spans = await get_trace_detail(db, "t1")
        assert trace is mock_trace
        assert len(spans) == 1

    @pytest.mark.asyncio
    async def test_get_trace_detail_not_found(self) -> None:
        from app.services.trace import get_trace_detail

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_trace_detail(db, "nonexistent")

    @pytest.mark.asyncio
    async def test_save_trace(self) -> None:
        from app.services.trace import save_trace

        db = _mock_db()
        trace = _make_orm(id="t1")
        spans = [_make_orm(id="s1"), _make_orm(id="s2")]
        await save_trace(db, trace, spans)
        db.add.assert_called_once()
        db.add_all.assert_called_once_with(spans)
        db.flush.assert_called_once()


# ── Provider Service ─────────────────────────────────────────────────────


class TestProviderService:
    """覆盖 services/provider.py 未覆盖函数 (25% → high%)。"""

    @pytest.mark.asyncio
    async def test_list_providers_with_filters(self) -> None:
        from app.services.provider import list_providers

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_providers(db, is_enabled=True, provider_type="openai")
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self) -> None:
        from app.services.provider import get_provider

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_provider(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_create_provider(self) -> None:
        from app.schemas.provider import ProviderCreate
        from app.services.provider import create_provider

        db = _mock_db()
        data = ProviderCreate(name="openai-1", provider_type="openai", base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("app.services.provider.encrypt_api_key", return_value="enc_key"):
            await create_provider(db, data)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_provider(self) -> None:
        from app.schemas.provider import ProviderUpdate
        from app.services.provider import update_provider

        mock_provider = _make_orm(
            id=uuid.uuid4(), name="p1", is_deleted=False, api_key_encrypted="old_enc",
        )
        db = _mock_db(_scalar_one_or_none(mock_provider))
        data = ProviderUpdate(name="p1-updated", api_key="new-key")
        with patch("app.services.provider.encrypt_api_key", return_value="new_enc"):
            await update_provider(db, mock_provider.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_provider(self) -> None:
        from app.services.provider import delete_provider

        mock_provider = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_provider))
        await delete_provider(db, mock_provider.id)
        assert mock_provider.is_deleted is True
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_provider(self) -> None:
        from app.services.provider import toggle_provider

        mock_provider = _make_orm(id=uuid.uuid4(), is_deleted=False, is_enabled=True)
        db = _mock_db(_scalar_one_or_none(mock_provider))
        await toggle_provider(db, mock_provider.id, False)
        assert mock_provider.is_enabled is False

    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        from app.services.provider import test_connection

        mock_provider = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            provider_type="openai", api_key_encrypted="enc_key",
            base_url="https://api.openai.com", auth_config=None,
            health_status="unknown", last_health_check=None,
        )
        db = _mock_db(_scalar_one_or_none(mock_provider))
        with patch("app.services.provider.decrypt_api_key", return_value="sk-test"), \
             patch("litellm.acompletion", new_callable=AsyncMock, return_value=MagicMock()):
            result = await test_connection(db, mock_provider.id)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self) -> None:
        from app.services.provider import test_connection

        mock_provider = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            provider_type="deepseek", api_key_encrypted="enc_key",
            base_url=None, auth_config=None,
            health_status="unknown", last_health_check=None,
        )
        db = _mock_db(_scalar_one_or_none(mock_provider))
        with patch("app.services.provider.decrypt_api_key", return_value="sk-test"), \
             patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("connection error")):
            result = await test_connection(db, mock_provider.id)
        assert result["success"] is False


# ── Provider Model Service ───────────────────────────────────────────────


class TestProviderModelService:
    """覆盖 services/provider_model.py。"""

    @pytest.mark.asyncio
    async def test_list_models(self) -> None:
        from app.services.provider_model import list_models

        db = _mock_db(_scalar_one(2), _scalars_all([_make_orm(), _make_orm()]))
        rows, total = await list_models(db, uuid.uuid4())
        assert total == 2

    @pytest.mark.asyncio
    async def test_create_model(self) -> None:
        from app.schemas.provider_model import ProviderModelCreate
        from app.services.provider_model import create_model

        pid = uuid.uuid4()
        db = _mock_db()
        data = ProviderModelCreate(model_name="gpt-4o", display_name="GPT-4o")
        await create_model(db, pid, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_model_not_found(self) -> None:
        from app.services.provider_model import get_model

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_model(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_model(self) -> None:
        from app.schemas.provider_model import ProviderModelUpdate
        from app.services.provider_model import update_model

        mock_model = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_model))
        data = ProviderModelUpdate(display_name="New Name")
        await update_model(db, mock_model.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_model(self) -> None:
        from app.services.provider_model import delete_model

        mock_model = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_model))
        await delete_model(db, mock_model.id)
        assert mock_model.is_deleted is True

    @pytest.mark.asyncio
    async def test_get_model_by_name(self) -> None:
        from app.services.provider_model import get_model_by_name

        mock_model = _make_orm(model_name="gpt-4o")
        db = _mock_db(_scalar_one_or_none(mock_model))
        result = await get_model_by_name(db, uuid.uuid4(), "gpt-4o")
        assert result is mock_model


# ── Agent Locale Service ─────────────────────────────────────────────────


class TestAgentLocaleService:
    """覆盖 services/agent_locale.py (25% → high%)。"""

    @pytest.mark.asyncio
    async def test_list_locales(self) -> None:
        from app.services.agent_locale import list_locales

        aid = uuid.uuid4()
        db = _mock_db(
            _scalar_one_or_none(aid),  # _get_agent_id_by_name → agent id
            _scalars_all([_make_orm(locale="en"), _make_orm(locale="zh")]),
        )
        result = await list_locales(db, "agent1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_create_locale(self) -> None:
        from app.schemas.agent_locale import AgentLocaleCreate
        from app.services.agent_locale import create_locale

        aid = uuid.uuid4()
        db = _mock_db(
            _scalar_one_or_none(aid),  # _get_agent_id_by_name
            _scalar_one_or_none(None),  # exists check → not duplicate
        )
        data = AgentLocaleCreate(locale="fr", instructions="Instructions en français")
        await create_locale(db, "agent1", data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_locale(self) -> None:
        from app.schemas.agent_locale import AgentLocaleUpdate
        from app.services.agent_locale import update_locale

        aid = uuid.uuid4()
        mock_locale = _make_orm(id=uuid.uuid4(), locale="en", agent_id=aid)
        db = _mock_db(
            _scalar_one_or_none(aid),
            _scalar_one_or_none(mock_locale),
        )
        data = AgentLocaleUpdate(instructions="Updated instructions")
        await update_locale(db, "agent1", "en", data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_locale(self) -> None:
        from app.services.agent_locale import delete_locale

        aid = uuid.uuid4()
        mock_locale = _make_orm(id=uuid.uuid4(), locale="en", agent_id=aid, is_default=False)
        db = _mock_db(
            _scalar_one_or_none(aid),
            _scalar_one_or_none(mock_locale),
        )
        await delete_locale(db, "agent1", "en")
        db.delete.assert_called_once()


# ── Agent Template Service ───────────────────────────────────────────────


class TestAgentTemplateService:
    """覆盖 services/agent_template.py (32% → high%)。"""

    @pytest.mark.asyncio
    async def test_create_template(self) -> None:
        from app.schemas.agent_template import AgentTemplateCreate
        from app.services.agent_template import create_template

        db = _mock_db()
        data = AgentTemplateCreate(
            name="t1", display_name="T1", category="general",
            description="desc", config={"model": "gpt-4o"},
        )
        await create_template(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_template_not_found(self) -> None:
        from app.services.agent_template import get_template

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_template(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_template_by_name(self) -> None:
        from app.services.agent_template import get_template_by_name

        mock_t = _make_orm(name="t1", is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_t))
        result = await get_template_by_name(db, "t1")
        assert result is mock_t

    @pytest.mark.asyncio
    async def test_list_templates(self) -> None:
        from app.services.agent_template import list_templates

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm(name="t1")]))
        rows, total = await list_templates(db, category="general")
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_template(self) -> None:
        from app.schemas.agent_template import AgentTemplateUpdate
        from app.services.agent_template import update_template

        mock_t = _make_orm(id=uuid.uuid4(), is_deleted=False, is_builtin=False)
        db = _mock_db(_scalar_one_or_none(mock_t))
        data = AgentTemplateUpdate(description="updated")
        await update_template(db, mock_t.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_template(self) -> None:
        from app.services.agent_template import delete_template

        mock_t = _make_orm(id=uuid.uuid4(), is_deleted=False, is_builtin=False)
        db = _mock_db(_scalar_one_or_none(mock_t))
        await delete_template(db, mock_t.id)
        assert mock_t.is_deleted is True


# ── Agent Version Service ────────────────────────────────────────────────


class TestAgentVersionService:
    """覆盖 services/agent_version.py。"""

    @pytest.mark.asyncio
    async def test_create_version(self) -> None:
        from app.services.agent_version import create_version

        db = _mock_db(_scalar_one(3))
        await create_version(db, uuid.uuid4(), {"name": "a1"})
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_versions(self) -> None:
        from app.services.agent_version import list_versions

        db = _mock_db(_scalar_one(2), _scalars_all([_make_orm(), _make_orm()]))
        rows, total = await list_versions(db, uuid.uuid4())
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_version_not_found(self) -> None:
        from app.services.agent_version import get_version

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_version(db, uuid.uuid4(), 1)

    @pytest.mark.asyncio
    async def test_rollback_to_version(self) -> None:
        from app.services.agent_version import rollback_to_version

        aid = uuid.uuid4()
        mock_version = _make_orm(
            id=uuid.uuid4(), agent_id=aid, version_number=2,
            snapshot={"name": "a1", "description": "d", "instructions": "i", "model": "m"},
        )
        mock_agent = _make_orm(
            id=aid, is_deleted=False, is_active=True,
            name="a1", description="d", instructions="i", model="m",
        )
        db = _mock_db(
            _scalar_one_or_none(mock_version),
            _scalar_one(3),
        )
        await rollback_to_version(db, mock_agent, 2)
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_agent_by_id_not_found(self) -> None:
        from app.services.agent_version import get_agent_by_id

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_agent_by_id(db, uuid.uuid4())


# ── Skill Service ────────────────────────────────────────────────────────


class TestSkillService:
    """覆盖 services/skill.py (33% → high%)。"""

    @pytest.mark.asyncio
    async def test_create_skill(self) -> None:
        from app.schemas.skill import SkillCreate
        from app.services.skill import create_skill

        db = _mock_db()
        data = SkillCreate(
            name="test-skill", content="# Skill Content\ndetails here",
        )
        await create_skill(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_skill_not_found(self) -> None:
        from app.services.skill import get_skill

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_skill(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_skill_by_name(self) -> None:
        from app.services.skill import get_skill_by_name

        mock_skill = _make_orm(name="s1")
        db = _mock_db(_scalar_one_or_none(mock_skill))
        result = await get_skill_by_name(db, "s1")
        assert result is mock_skill

    @pytest.mark.asyncio
    async def test_list_skills(self) -> None:
        from app.services.skill import list_skills

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm()]))
        rows, total = await list_skills(db, category="public", tag="test")
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_skill(self) -> None:
        from app.schemas.skill import SkillUpdate
        from app.services.skill import update_skill

        mock_skill = _make_orm(id=uuid.uuid4(), is_deleted=False, updated_at=datetime.now(UTC))
        db = _mock_db(_scalar_one_or_none(mock_skill))
        data = SkillUpdate(description="Updated")
        await update_skill(db, mock_skill.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_skill(self) -> None:
        from app.services.skill import delete_skill

        mock_skill = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_skill))
        await delete_skill(db, mock_skill.id)
        assert mock_skill.is_deleted is True

    @pytest.mark.asyncio
    async def test_search_skills(self) -> None:
        from app.schemas.skill import SkillSearchRequest
        from app.services.skill import search_skills

        db = _mock_db(_scalars_all([_make_orm(name="s1")]))
        data = SkillSearchRequest(query="test")
        result = await search_skills(db, data)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_skills_for_agent(self) -> None:
        from app.services.skill import find_skills_for_agent

        db = _mock_db(_scalars_all([_make_orm(name="skill1")]))
        result = await find_skills_for_agent(db, "agent1")
        assert len(result) == 1


# ── Memory Service ───────────────────────────────────────────────────────


class TestMemoryService:
    """覆盖 services/memory.py (35% → high%)。"""

    @pytest.mark.asyncio
    async def test_create_memory(self) -> None:
        from app.schemas.memory import MemoryCreate
        from app.services.memory import create_memory

        db = _mock_db()
        data = MemoryCreate(
            type="user_profile", content="remember this",
            user_id="u1", confidence=0.9,
        )
        await create_memory(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self) -> None:
        from app.services.memory import get_memory

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_memory(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_memories(self) -> None:
        from app.services.memory import list_memories

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm()]))
        rows, total = await list_memories(db, agent_name="a1", user_id="u1", memory_type="user_profile")
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_memory(self) -> None:
        from app.schemas.memory import MemoryUpdate
        from app.services.memory import update_memory

        mock_mem = _make_orm(id=uuid.uuid4(), is_deleted=False, updated_at=datetime.now(UTC))
        db = _mock_db(_scalar_one_or_none(mock_mem))
        data = MemoryUpdate(content="updated")
        await update_memory(db, mock_mem.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory(self) -> None:
        from app.services.memory import delete_memory

        mock_mem = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_mem))
        await delete_memory(db, mock_mem.id)
        assert mock_mem.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_user_memories(self) -> None:
        from app.services.memory import delete_user_memories

        db = _mock_db(_rowcount(3))
        count = await delete_user_memories(db, "user1")
        assert count == 3
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_memories(self) -> None:
        from app.schemas.memory import MemorySearchRequest
        from app.services.memory import search_memories

        db = _mock_db(_scalars_all([_make_orm()]))
        data = MemorySearchRequest(user_id="u1", query="keyword")
        result = await search_memories(db, data)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_decay_memories(self) -> None:
        from app.schemas.memory import MemoryDecayRequest
        from app.services.memory import decay_memories

        db = _mock_db(_rowcount(5))
        data = MemoryDecayRequest(before=datetime.now(UTC), rate=0.05)
        count = await decay_memories(db, data)
        assert count == 5


# ── Token Usage Service ──────────────────────────────────────────────────


class TestTokenUsageService:
    """覆盖 services/token_usage.py。"""

    @pytest.mark.asyncio
    async def test_create_token_usage_logs(self) -> None:
        from app.services.token_usage import create_token_usage_logs

        db = _mock_db()
        logs = [_make_orm()]
        await create_token_usage_logs(db, logs)
        db.add_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_token_usage(self) -> None:
        from app.services.token_usage import list_token_usage

        db = _mock_db(_scalar_one(5), _scalars_all([_make_orm()]))
        rows, total = await list_token_usage(db, agent_name="a1", model="gpt-4o")
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_token_usage_summary(self) -> None:
        from app.services.token_usage import get_token_usage_summary

        row1 = MagicMock()
        row1.dimension = "gpt-4o"
        row1.agent_name = "agent1"
        row1.model = "gpt-4o"
        row1.total_prompt = 1000
        row1.total_completion = 500
        row1.total_tokens = 1500
        row1.count = 10
        db = _mock_db(_rows([row1]))
        result = await get_token_usage_summary(db, group_by="agent_model")
        assert len(result) >= 1


# ── IM Channel Service ──────────────────────────────────────────────────


class TestIMChannelService:
    """覆盖 services/im_channel.py。"""

    @pytest.mark.asyncio
    async def test_list_channels(self) -> None:
        from app.services.im_channel import list_channels

        db = _mock_db(_scalar(1), _scalars_all([_make_orm()]))
        rows, total = await list_channels(db)
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_channel(self) -> None:
        from app.schemas.im_channel import IMChannelCreate
        from app.services.im_channel import create_channel

        db = _mock_db()
        data = IMChannelCreate(
            name="ch1", channel_type="webhook",
            agent_name="a1", config={},
        )
        await create_channel(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_channel_not_found(self) -> None:
        from app.services.im_channel import get_channel

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_channel(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_channel(self) -> None:
        from app.schemas.im_channel import IMChannelUpdate
        from app.services.im_channel import update_channel

        mock_ch = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_ch))
        data = IMChannelUpdate(name="updated")
        await update_channel(db, mock_ch.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_channel(self) -> None:
        from app.services.im_channel import delete_channel

        mock_ch = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_ch))
        result = await delete_channel(db, mock_ch.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature(self) -> None:
        import hashlib
        import hmac

        from app.services.im_channel import verify_webhook_signature

        secret = "mysecret"
        payload = b"test body"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(secret, payload, sig) is True
        assert verify_webhook_signature(secret, payload, "invalid") is False

    @pytest.mark.asyncio
    async def test_route_message(self) -> None:
        from app.services.im_channel import route_message

        mock_ch = _make_orm(
            id=uuid.uuid4(), is_deleted=False, is_enabled=True,
            agent_id=uuid.uuid4(), agent_name="a1", name="ch1",
        )
        db = _mock_db()
        db.get = AsyncMock(return_value=mock_ch)
        result = await route_message(db, mock_ch.id, "user1", "hello")
        assert result["status"] == "accepted"


# ── Supervision Service ──────────────────────────────────────────────────


class TestSupervisionService:
    """覆盖 services/supervision.py — 返回 Pydantic 对象。"""

    @pytest.mark.asyncio
    async def test_list_active_sessions(self) -> None:
        from app.services.supervision import list_active_sessions

        session_orm = _make_orm(
            id=uuid.uuid4(), agent_name="a1", status="active",
            title="test", created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        row = (session_orm, 100, 5)
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        db = _mock_db()
        db.execute = AsyncMock(return_value=result_mock)
        resp = await list_active_sessions(db)
        assert resp.total == 1
        assert resp.data[0].agent_name == "a1"

    @pytest.mark.asyncio
    async def test_get_session_detail(self) -> None:
        from app.services.supervision import get_session_detail

        session_orm = _make_orm(
            id=uuid.uuid4(), agent_name="a1", status="active",
            title="test", created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC), metadata_={},
        )
        session_result = _scalar_one_or_none(session_orm)
        token_row = MagicMock()
        token_row.__getitem__ = lambda self, idx: [0, 0][idx]
        token_result = MagicMock()
        token_result.one.return_value = token_row
        db = _mock_db(session_result, token_result)
        resp = await get_session_detail(db, session_orm.id)
        assert resp.agent_name == "a1"

    @pytest.mark.asyncio
    async def test_get_session_detail_not_found(self) -> None:
        from app.services.supervision import get_session_detail

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_session_detail(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_pause_session(self) -> None:
        from app.services.supervision import pause_session

        session_orm = _make_orm(
            id=uuid.uuid4(), status="active",
            agent_name="a1", title="test",
        )
        db = _mock_db(_scalar_one_or_none(session_orm))
        resp = await pause_session(db, session_orm.id)
        assert session_orm.status == "paused"
        assert resp.session_id == session_orm.id

    @pytest.mark.asyncio
    async def test_pause_session_wrong_status(self) -> None:
        from app.services.supervision import pause_session

        session_orm = _make_orm(id=uuid.uuid4(), status="paused")
        db = _mock_db(_scalar_one_or_none(session_orm))
        with pytest.raises(ConflictError):
            await pause_session(db, session_orm.id)

    @pytest.mark.asyncio
    async def test_resume_session(self) -> None:
        from app.services.supervision import resume_session

        session_orm = _make_orm(id=uuid.uuid4(), status="paused")
        db = _mock_db(_scalar_one_or_none(session_orm))
        await resume_session(db, session_orm.id)
        assert session_orm.status == "active"


# ── Evaluation Service ───────────────────────────────────────────────────


class TestEvaluationService:
    """覆盖 services/evaluation.py。"""

    @pytest.mark.asyncio
    async def test_create_evaluation(self) -> None:
        from app.schemas.evaluation import RunEvaluationCreate
        from app.services.evaluation import create_evaluation

        db = _mock_db()
        data = RunEvaluationCreate(
            run_id="run1", agent_id=uuid.uuid4(),
            accuracy=0.9, relevance=0.85, coherence=0.8,
            helpfulness=0.88, safety=1.0, efficiency=0.7, tool_usage=0.6,
        )
        await create_evaluation(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_evaluations(self) -> None:
        from app.services.evaluation import list_evaluations

        db = _mock_db(_scalar(1), _scalars_all([_make_orm()]))
        rows, total = await list_evaluations(db, agent_id=uuid.uuid4())
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_evaluation_found(self) -> None:
        from app.services.evaluation import get_evaluation

        mock_eval = _make_orm(id=uuid.uuid4())
        db = _mock_db()
        db.get = AsyncMock(return_value=mock_eval)
        result = await get_evaluation(db, mock_eval.id)
        assert result is mock_eval

    @pytest.mark.asyncio
    async def test_get_evaluation_not_found(self) -> None:
        from app.services.evaluation import get_evaluation

        db = _mock_db()
        db.get = AsyncMock(return_value=None)
        result = await get_evaluation(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_create_feedback(self) -> None:
        from app.schemas.evaluation import RunFeedbackCreate
        from app.services.evaluation import create_feedback

        db = _mock_db()
        data = RunFeedbackCreate(run_id="run1", rating=1, comment="great")
        await create_feedback(db, data, user_id=uuid.uuid4())
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_feedbacks(self) -> None:
        from app.services.evaluation import list_feedbacks

        db = _mock_db(_scalar(3), _scalars_all([_make_orm()]))
        rows, total = await list_feedbacks(db, run_id="run1")
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_agent_quality_summary(self) -> None:
        from app.services.evaluation import get_agent_quality_summary

        eval_row = MagicMock()
        eval_row.eval_count = 10
        eval_row.avg_accuracy = 0.85
        eval_row.avg_relevance = 0.9
        eval_row.avg_coherence = 0.88
        eval_row.avg_helpfulness = 0.92
        eval_row.avg_safety = 1.0
        eval_row.avg_efficiency = 0.8
        eval_row.avg_tool_usage = 0.7
        eval_row.avg_overall = 0.86
        eval_result = MagicMock()
        eval_result.one.return_value = eval_row

        fb_row = MagicMock()
        fb_row.total = 5
        fb_row.positive = 4
        fb_result = MagicMock()
        fb_result.one.return_value = fb_row

        db = _mock_db(eval_result, fb_result)
        result = await get_agent_quality_summary(db, uuid.uuid4())
        assert result.eval_count == 10
        assert result.positive_rate == 0.8


# ── APM Service ──────────────────────────────────────────────────────────


class TestAPMService:
    """覆盖 services/apm.py。"""

    @pytest.mark.asyncio
    async def test_get_apm_dashboard(self) -> None:
        from app.schemas.apm import ApmOverview
        from app.services.apm import get_apm_dashboard

        overview = ApmOverview(
            total_traces=10, total_spans=50, avg_duration_ms=150.0,
            error_rate=0.1, total_tokens=5000, active_agents=3,
        )
        with patch("app.services.apm._get_overview", AsyncMock(return_value=overview)), \
             patch("app.services.apm._get_agent_ranking", AsyncMock(return_value=[])), \
             patch("app.services.apm._get_model_usage", AsyncMock(return_value=[])), \
             patch("app.services.apm._get_daily_trend", AsyncMock(return_value=[])), \
             patch("app.services.apm._get_tool_usage", AsyncMock(return_value=[])):
            db = AsyncMock()
            result = await get_apm_dashboard(db)
            assert result.overview.total_traces == 10


# ── MCP Server Service ──────────────────────────────────────────────────


class TestMCPServerService:
    """覆盖 services/mcp_server.py (38% → high%)。"""

    @pytest.mark.asyncio
    async def test_create_mcp_server(self) -> None:
        from app.schemas.mcp_server import MCPServerCreate
        from app.services.mcp_server import create_mcp_server

        db = _mock_db(_scalar_one_or_none(None))
        data = MCPServerCreate(
            name="mcp1", transport_type="stdio",
            command="python", args=["-m", "server"],
        )
        await create_mcp_server(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_mcp_server_not_found(self) -> None:
        from app.services.mcp_server import get_mcp_server

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_mcp_server(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_mcp_server_by_name(self) -> None:
        from app.services.mcp_server import get_mcp_server_by_name

        mock_s = _make_orm(name="mcp1", is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_s))
        result = await get_mcp_server_by_name(db, "mcp1")
        assert result is mock_s

    @pytest.mark.asyncio
    async def test_list_mcp_servers(self) -> None:
        from app.services.mcp_server import list_mcp_servers

        db = _mock_db(_scalar_one(2), _scalars_all([_make_orm(), _make_orm()]))
        rows, total = await list_mcp_servers(db, transport_type="stdio", is_enabled=True)
        assert total == 2

    @pytest.mark.asyncio
    async def test_update_mcp_server(self) -> None:
        from app.schemas.mcp_server import MCPServerUpdate
        from app.services.mcp_server import update_mcp_server

        mock_s = _make_orm(id=uuid.uuid4(), is_deleted=False, auth_config=None)
        db = _mock_db(_scalar_one_or_none(mock_s))
        data = MCPServerUpdate(description="updated")
        await update_mcp_server(db, mock_s.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_mcp_server(self) -> None:
        from app.services.mcp_server import delete_mcp_server

        mock_s = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_s))
        await delete_mcp_server(db, mock_s.id)
        assert mock_s.is_deleted is True

    @pytest.mark.asyncio
    async def test_get_mcp_servers_by_names(self) -> None:
        from app.services.mcp_server import get_mcp_servers_by_names

        db = _mock_db(_scalars_all([_make_orm(name="mcp1")]))
        result = await get_mcp_servers_by_names(db, ["mcp1", "mcp2"])
        assert len(result) == 1


# ── Config Change Service ────────────────────────────────────────────────


class TestConfigChangeService:
    """覆盖 services/config_change.py。"""

    @pytest.mark.asyncio
    async def test_record_change(self) -> None:
        from app.schemas.config_change_log import ConfigChangeLogCreate
        from app.services.config_change import record_change

        db = _mock_db()
        data = ConfigChangeLogCreate(
            config_key="agent.instructions",
            entity_type="agent", entity_id="a1",
            old_value={"name": "old"}, new_value={"name": "new"},
        )
        await record_change(db, data, changed_by=uuid.uuid4())
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_change_logs(self) -> None:
        from app.services.config_change import list_change_logs

        db = _mock_db()
        db.scalar = AsyncMock(return_value=3)
        db.execute = AsyncMock(return_value=_scalars_all([_make_orm()]))
        rows, total = await list_change_logs(db, entity_type="agent", entity_id="a1")
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_change_log_not_found(self) -> None:
        from app.services.config_change import get_change_log

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_change_log(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_rollback_change(self) -> None:
        from app.services.config_change import rollback_change

        mock_log = _make_orm(
            id=uuid.uuid4(), config_key="agent.name",
            entity_type="agent", entity_id="a1",
            old_value={"name": "old"}, new_value={"name": "new"},
            changed_by=None, change_source="api",
        )
        db = _mock_db()
        await rollback_change(db, mock_log, changed_by=uuid.uuid4())
        db.add.assert_called_once()


# ── Scheduled Task Service ───────────────────────────────────────────────


class TestScheduledTaskService:
    """覆盖 services/scheduled_task.py。"""

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks(self) -> None:
        from app.services.scheduled_task import list_scheduled_tasks

        db = _mock_db(_scalars_all([_make_orm()]))
        db.scalar = AsyncMock(return_value=1)
        rows, total = await list_scheduled_tasks(db)
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_scheduled_task_not_found(self) -> None:
        from app.services.scheduled_task import get_scheduled_task

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_scheduled_task(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_create_scheduled_task(self) -> None:
        from app.schemas.scheduled_task import ScheduledTaskCreate
        from app.services.scheduled_task import create_scheduled_task

        db = _mock_db()
        data = ScheduledTaskCreate(
            name="task1", agent_id=uuid.uuid4(),
            cron_expr="*/5 * * * *", input_text="do something",
        )
        await create_scheduled_task(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_scheduled_task(self) -> None:
        from app.schemas.scheduled_task import ScheduledTaskUpdate
        from app.services.scheduled_task import update_scheduled_task

        mock_task = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            cron_expr="*/5 * * * *",
        )
        data = ScheduledTaskUpdate(cron_expr="*/10 * * * *")
        db = _mock_db()
        await update_scheduled_task(db, mock_task, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_scheduled_task(self) -> None:
        from app.services.scheduled_task import delete_scheduled_task

        mock_task = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db()
        await delete_scheduled_task(db, mock_task)
        assert mock_task.is_deleted is True

    @pytest.mark.asyncio
    async def test_get_due_tasks(self) -> None:
        from app.services.scheduled_task import get_due_tasks

        db = _mock_db(_scalars_all([_make_orm()]))
        result = await get_due_tasks(db)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_mark_task_executed(self) -> None:
        from app.services.scheduled_task import mark_task_executed

        mock_task = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            cron_expr="*/5 * * * *",
        )
        db = _mock_db()
        await mark_task_executed(db, mock_task)
        db.commit.assert_called_once()


# ── Role Service ─────────────────────────────────────────────────────────


class TestRoleService:
    """覆盖 services/role.py (44% → high%)。"""

    @pytest.mark.asyncio
    async def test_create_role(self) -> None:
        from app.schemas.role import RoleCreate
        from app.services.role import create_role

        db = _mock_db()
        data = RoleCreate(name="editor-role", description="Editor role", permissions={"agents": ["read", "write"]})
        await create_role(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_role_not_found(self) -> None:
        from app.services.role import get_role

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_role(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_role_by_name(self) -> None:
        from app.services.role import get_role_by_name

        mock_role = _make_orm(name="admin")
        db = _mock_db(_scalar_one_or_none(mock_role))
        result = await get_role_by_name(db, "admin")
        assert result is mock_role

    @pytest.mark.asyncio
    async def test_list_roles(self) -> None:
        from app.services.role import list_roles

        db = _mock_db(_scalar(2), _scalars_all([_make_orm(), _make_orm()]))
        rows, total = await list_roles(db)
        assert total == 2
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_update_role(self) -> None:
        from app.schemas.role import RoleUpdate
        from app.services.role import update_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=False)
        db = _mock_db(_scalar_one_or_none(mock_role))
        data = RoleUpdate(description="updated")
        await update_role(db, mock_role.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_role(self) -> None:
        from app.services.role import delete_role

        mock_role = _make_orm(id=uuid.uuid4(), is_system=False)
        db = _mock_db(
            _scalar_one_or_none(mock_role),
            _scalar(0),
        )
        await delete_role(db, mock_role.id)
        db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_role_to_user(self) -> None:
        from app.services.role import assign_role_to_user

        mock_user = _make_orm(id=uuid.uuid4(), role_id=None)
        mock_role = _make_orm(id=uuid.uuid4(), is_system=False)
        db = _mock_db(
            _scalar_one_or_none(mock_user),
            _scalar_one_or_none(mock_role),
        )
        await assign_role_to_user(db, mock_user.id, mock_role.id)
        db.commit.assert_called_once()

    def test_check_permission_true(self) -> None:
        from app.services.role import check_permission

        perms: dict = {"agents": ["read", "write"]}
        assert check_permission(perms, "agents", "read") is True

    def test_check_permission_false(self) -> None:
        from app.services.role import check_permission

        perms: dict = {"agents": ["read"]}
        assert check_permission(perms, "agents", "write") is False

    def test_check_permission_wildcard(self) -> None:
        from app.services.role import check_permission

        perms: dict = {"agents": ["read", "write", "delete"]}
        assert check_permission(perms, "agents", "delete") is True
        assert check_permission(perms, "providers", "read") is False


# ── Rate Limiter Service ─────────────────────────────────────────────────


class TestRateLimiterService:
    """覆盖 services/rate_limiter.py (0% → high%)。"""

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_limits(self) -> None:
        from app.services.rate_limiter import check_rate_limit

        await check_rate_limit(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_check_rate_limit_rpm_ok(self) -> None:
        from app.services.rate_limiter import check_rate_limit

        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.services.rate_limiter.get_redis", AsyncMock(return_value=mock_redis)):
            await check_rate_limit(uuid.uuid4(), rpm_limit=100)

    @pytest.mark.asyncio
    async def test_check_rate_limit_rpm_exceeded(self) -> None:
        from app.services.rate_limiter import RateLimitExceeded, check_rate_limit

        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 100, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.zremrangebyscore = AsyncMock()

        with patch("app.services.rate_limiter.get_redis", AsyncMock(return_value=mock_redis)), \
             pytest.raises(RateLimitExceeded):
            await check_rate_limit(uuid.uuid4(), rpm_limit=100)

    @pytest.mark.asyncio
    async def test_check_rate_limit_tpm_ok(self) -> None:
        from app.services.rate_limiter import check_rate_limit

        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, [b"100:123.45"]])

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.services.rate_limiter.get_redis", AsyncMock(return_value=mock_redis)):
            await check_rate_limit(uuid.uuid4(), tpm_limit=10000, token_count=500)

    @pytest.mark.asyncio
    async def test_check_rate_limit_tpm_exceeded(self) -> None:
        from app.services.rate_limiter import RateLimitExceeded, check_rate_limit

        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, [b"9500:123.45"]])

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.services.rate_limiter.get_redis", AsyncMock(return_value=mock_redis)), \
             pytest.raises(RateLimitExceeded):
            await check_rate_limit(uuid.uuid4(), tpm_limit=10000, token_count=600)

    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self) -> None:
        from app.services.rate_limiter import get_rate_limit_status

        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 42, 0, [b"300:123.45", b"500:456.78"]])

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.services.rate_limiter.get_redis", AsyncMock(return_value=mock_redis)):
            result = await get_rate_limit_status(uuid.uuid4())
        assert result["current_rpm"] == 42
        assert result["current_tpm"] == 800


# ── Guardrail Service ────────────────────────────────────────────────────


class TestGuardrailService:
    """覆盖 services/guardrail.py — 使用 keyword-only 参数。"""

    @pytest.mark.asyncio
    async def test_list_guardrail_rules(self) -> None:
        from app.services.guardrail import list_guardrail_rules

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm()]))
        rows, total = await list_guardrail_rules(db, type_filter="input", mode_filter="regex")
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_guardrail_rule(self) -> None:
        from app.services.guardrail import create_guardrail_rule

        db = _mock_db(_scalar_one_or_none(None))  # name不存在
        await create_guardrail_rule(
            db, name="g1", description="desc",
            type_="input", mode="regex",
            config={"patterns": ["bad.*word"]},
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_guardrail_rule_not_found(self) -> None:
        from app.services.guardrail import get_guardrail_rule

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_guardrail_rule(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_guardrail_rule(self) -> None:
        from app.services.guardrail import update_guardrail_rule

        mock_g = _make_orm(
            id=uuid.uuid4(), is_deleted=False,
            type="input", mode="regex", config={"pattern": "old"},
        )
        db = _mock_db(_scalar_one_or_none(mock_g))
        await update_guardrail_rule(db, mock_g.id, description="updated")
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_guardrail_rule(self) -> None:
        from app.services.guardrail import delete_guardrail_rule

        mock_g = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_g))
        await delete_guardrail_rule(db, mock_g.id)
        assert mock_g.is_deleted is True

    @pytest.mark.asyncio
    async def test_get_guardrail_rules_by_names(self) -> None:
        from app.services.guardrail import get_guardrail_rules_by_names

        db = _mock_db(_scalars_all([_make_orm(name="g1")]))
        result = await get_guardrail_rules_by_names(db, ["g1"])
        assert len(result) == 1


# ── Approval Service ─────────────────────────────────────────────────────


class TestApprovalService:
    """覆盖 services/approval.py。"""

    @pytest.mark.asyncio
    async def test_list_approval_requests(self) -> None:
        from app.services.approval import list_approval_requests

        db = _mock_db(_scalar(1), _scalars_all([_make_orm()]))
        rows, total = await list_approval_requests(db, status="pending")
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_approval_request_not_found(self) -> None:
        from app.services.approval import get_approval_request

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_approval_request(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_resolve_approval_approve(self) -> None:
        from app.services.approval import resolve_approval_request

        mock_approval = _make_orm(
            id=uuid.uuid4(), status="pending",
            session_id=str(uuid.uuid4()), agent_name="a1",
            tool_name="t1", tool_args={"x": 1},
        )
        db = _mock_db(_scalar_one_or_none(mock_approval))
        with patch("app.services.approval.ApprovalManager") as MockMgr:
            mock_mgr = MagicMock()
            mock_mgr.resolve = AsyncMock()
            MockMgr.return_value = mock_mgr
            await resolve_approval_request(db, mock_approval.id, action="approve")

    @pytest.mark.asyncio
    async def test_resolve_approval_reject(self) -> None:
        from app.services.approval import resolve_approval_request

        mock_approval = _make_orm(
            id=uuid.uuid4(), status="pending",
            session_id=str(uuid.uuid4()), agent_name="a1",
            tool_name="t1", tool_args={"x": 1},
        )
        db = _mock_db(_scalar_one_or_none(mock_approval))
        with patch("app.services.approval.ApprovalManager") as MockMgr:
            mock_mgr = MagicMock()
            mock_mgr.resolve = AsyncMock()
            MockMgr.return_value = mock_mgr
            await resolve_approval_request(db, mock_approval.id, action="reject")


# ── Workflow Service ─────────────────────────────────────────────────────


class TestWorkflowService:
    """覆盖 services/workflow.py。"""

    @pytest.mark.asyncio
    async def test_create_workflow(self) -> None:
        from app.schemas.workflow import WorkflowCreate
        from app.services.workflow import create_workflow

        db = _mock_db(_scalar_one_or_none(None))
        data = WorkflowCreate(
            name="wf1", description="desc", steps=[], edges=[],
        )
        await create_workflow(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self) -> None:
        from app.services.workflow import get_workflow

        db = _mock_db(_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await get_workflow(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_workflows(self) -> None:
        from app.services.workflow import list_workflows

        db = _mock_db(_scalar_one(1), _scalars_all([_make_orm()]))
        rows, total = await list_workflows(db)
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_workflow(self) -> None:
        from app.schemas.workflow import WorkflowUpdate
        from app.services.workflow import update_workflow

        mock_wf = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_wf))
        data = WorkflowUpdate(description="updated")
        await update_workflow(db, mock_wf.id, data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_workflow(self) -> None:
        from app.services.workflow import delete_workflow

        mock_wf = _make_orm(id=uuid.uuid4(), is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_wf))
        await delete_workflow(db, mock_wf.id)
        assert mock_wf.is_deleted is True

    def test_validate_workflow_definition(self) -> None:
        from app.services.workflow import validate_workflow_definition

        errors = validate_workflow_definition(steps=[], edges=[])
        assert isinstance(errors, list)


# ── Alert Service ────────────────────────────────────────────────────────


class TestAlertService:
    """覆盖 services/alert.py。"""

    @pytest.mark.asyncio
    async def test_list_alert_rules(self) -> None:
        from app.services.alert import list_alert_rules

        db = _mock_db(_scalars_all([_make_orm(), _make_orm()]))
        db.scalar = AsyncMock(return_value=2)
        rows, total = await list_alert_rules(db, is_enabled=True)
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_alert_rule_not_found(self) -> None:
        from app.services.alert import get_alert_rule

        db = _mock_db(_scalar_one_or_none(None))
        result = await get_alert_rule(db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_create_alert_rule(self) -> None:
        from app.schemas.alert import AlertRuleCreate
        from app.services.alert import create_alert_rule

        db = _mock_db()
        data = AlertRuleCreate(
            name="high-error",
            metric="error_rate",
            operator=">",
            threshold=0.1,
            window_minutes=5,
        )
        await create_alert_rule(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_alert_events(self) -> None:
        from app.services.alert import list_alert_events

        db = _mock_db(_scalars_all([_make_orm(), _make_orm()]))
        db.scalar = AsyncMock(return_value=2)
        rows, total = await list_alert_events(db, rule_id=uuid.uuid4())
        assert total == 2

    @pytest.mark.asyncio
    async def test_evaluate_all_rules(self) -> None:
        from app.services.alert import evaluate_all_rules

        mock_rule = _make_orm(
            id=uuid.uuid4(), name="rule1", is_enabled=True,
            metric="error_rate", operator=">", threshold=0.1,
            window_minutes=5, cooldown_minutes=10,
            notification_channels=[], last_triggered_at=None,
            agent_name=None, severity="warning",
        )
        db = _mock_db(
            _scalars_all([mock_rule]),
        )
        with patch("app.services.alert._compute_metric", AsyncMock(return_value=0.05)):
            result = await evaluate_all_rules(db)
        assert result == []


# ── Agent Service ────────────────────────────────────────────────────────


class TestAgentService:
    """覆盖 services/agent.py 未覆盖行。"""

    @pytest.mark.asyncio
    async def test_list_agents_with_search(self) -> None:
        from app.services.agent import list_agents

        db = _mock_db(_scalar_one(0), _scalars_all([]))
        rows, total = await list_agents(db, search="test")
        assert total == 0

    @pytest.mark.asyncio
    async def test_create_agent(self) -> None:
        from app.schemas.agent import AgentCreate
        from app.services.agent import create_agent

        db = _mock_db(
            _scalar_one_or_none(None),
        )
        data = AgentCreate(
            name="test-agent", description="test",
            instructions="you are test", model="gpt-4o",
        )
        with patch("app.services.agent.create_version", AsyncMock()):
            await create_agent(db, data)
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_create_agent_conflict(self) -> None:
        from app.schemas.agent import AgentCreate
        from app.services.agent import create_agent

        db = _mock_db(_scalar_one_or_none(uuid.uuid4()))
        data = AgentCreate(
            name="dup-agent", description="test",
            instructions="you are test", model="gpt-4o",
        )
        with pytest.raises(ConflictError):
            await create_agent(db, data)

    @pytest.mark.asyncio
    async def test_update_agent(self) -> None:
        from app.schemas.agent import AgentUpdate
        from app.services.agent import update_agent

        mock_agent = _make_orm(
            id=uuid.uuid4(), name="test-agent",
            is_active=True, is_deleted=False,
        )
        db = _mock_db(_scalar_one_or_none(mock_agent))
        data = AgentUpdate(description="updated desc")
        with patch("app.services.agent.create_version", AsyncMock()), \
             patch("app.services.agent._snapshot_from_agent", return_value={}):
            await update_agent(db, "test-agent", data)
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_agent(self) -> None:
        from app.services.agent import delete_agent

        mock_agent = _make_orm(
            id=uuid.uuid4(), name="test-agent",
            is_active=True, is_deleted=False,
        )
        db = _mock_db(_scalar_one_or_none(mock_agent))
        await delete_agent(db, "test-agent")
        assert mock_agent.is_deleted is True


# ── Tool Group Service ───────────────────────────────────────────────────


class TestToolGroupServiceExtra:
    """覆盖 services/tool_group.py 未覆盖行。"""

    @pytest.mark.asyncio
    async def test_create_tool_group(self) -> None:
        from app.schemas.tool_group import ToolGroupCreate
        from app.services.tool_group import create_tool_group

        db = _mock_db(_scalar_one_or_none(None))  # name 不存在
        data = ToolGroupCreate(
            name="tg1", description="desc", tools=[],
        )
        await create_tool_group(db, data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tool_group(self) -> None:
        from app.schemas.tool_group import ToolGroupUpdate
        from app.services.tool_group import update_tool_group

        mock_tg = _make_orm(id=uuid.uuid4(), name="tg1", is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_tg))
        data = ToolGroupUpdate(description="updated")
        await update_tool_group(db, "tg1", data)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_tool_group(self) -> None:
        from app.services.tool_group import delete_tool_group

        mock_tg = _make_orm(id=uuid.uuid4(), name="tg1", is_deleted=False)
        db = _mock_db(_scalar_one_or_none(mock_tg))
        await delete_tool_group(db, "tg1")
        assert mock_tg.is_deleted is True
