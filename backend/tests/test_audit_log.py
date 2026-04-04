"""审计日志（AuditLog）测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogListResponse, AuditLogQuery, AuditLogResponse
from app.services.audit_log import create_audit_log, list_audit_logs, get_audit_log


# ─── Schema 测试 ───


class TestAuditLogSchemas:
    """审计日志 Schema 测试。"""

    def test_response_from_attributes(self) -> None:
        resp = AuditLogResponse(
            id=uuid.uuid4(),
            user_id="user-1",
            action="CREATE",
            resource_type="agents",
            resource_id="agent-1",
            detail={"path": "/api/v1/agents", "method": "POST"},
            ip_address="192.168.1.1",
            user_agent="test-agent",
            request_id="req-123",
            status_code=201,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.action == "CREATE"
        assert resp.resource_type == "agents"

    def test_list_response(self) -> None:
        resp = AuditLogListResponse(items=[], total=0)
        assert resp.total == 0
        assert resp.items == []

    def test_query_defaults(self) -> None:
        q = AuditLogQuery()
        assert q.limit == 20
        assert q.offset == 0
        assert q.action is None
        assert q.resource_type is None

    def test_query_with_filters(self) -> None:
        q = AuditLogQuery(action="CREATE", resource_type="agents", user_id="u1")
        assert q.action == "CREATE"
        assert q.resource_type == "agents"
        assert q.user_id == "u1"


# ─── Service 测试 ───


class TestAuditLogService:
    """审计日志 Service 测试。"""

    @pytest.mark.asyncio
    async def test_create_audit_log(self) -> None:
        db = AsyncMock()
        db.commit = AsyncMock()

        record = await create_audit_log(
            db,
            user_id="user-1",
            action="CREATE",
            resource_type="agents",
            resource_id="agent-1",
            detail={"path": "/api/v1/agents"},
            ip_address="127.0.0.1",
        )
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_audit_logs(self) -> None:
        db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        mock_rows_result = MagicMock()
        mock_rows_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        rows, total = await list_audit_logs(db, limit=10, offset=0)
        assert total == 2
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filters(self) -> None:
        db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_rows_result = MagicMock()
        mock_rows_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        rows, total = await list_audit_logs(
            db,
            action="DELETE",
            resource_type="agents",
            user_id="u1",
            resource_id="a1",
        )
        assert total == 0
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_get_audit_log(self) -> None:
        mock_record = MagicMock(spec=AuditLog)
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_audit_log(db, uuid.uuid4())
        assert result is mock_record

    @pytest.mark.asyncio
    async def test_get_audit_log_not_found(self) -> None:
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_audit_log(db, uuid.uuid4())
        assert result is None


# ─── API 测试 ───


class TestAuditLogAPI:
    """审计日志 API 测试。"""

    @pytest.mark.asyncio
    async def test_list_audit_logs(self) -> None:
        from app.api.audit_logs import list_audit_logs as api_list
        mock_rows = []
        with patch("app.api.audit_logs.audit_log_service.list_audit_logs", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = (mock_rows, 0)
            result = await api_list(
                limit=20,
                offset=0,
                action=None,
                resource_type=None,
                user_id=None,
                resource_id=None,
                db=AsyncMock(),
            )
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_get_audit_log_found(self) -> None:
        from app.api.audit_logs import get_audit_log as api_get
        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.user_id = "user-1"
        mock_record.action = "CREATE"
        mock_record.resource_type = "agents"
        mock_record.resource_id = "agent-1"
        mock_record.detail = {}
        mock_record.ip_address = "127.0.0.1"
        mock_record.user_agent = "test"
        mock_record.request_id = "req-1"
        mock_record.status_code = 201
        mock_record.created_at = datetime.now(timezone.utc)
        with patch("app.api.audit_logs.audit_log_service.get_audit_log", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = mock_record
            result = await api_get(log_id=mock_record.id, db=AsyncMock())
        assert result.action == "CREATE"

    @pytest.mark.asyncio
    async def test_get_audit_log_not_found(self) -> None:
        from app.api.audit_logs import get_audit_log as api_get
        from app.core.exceptions import NotFoundError
        with patch("app.api.audit_logs.audit_log_service.get_audit_log", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = None
            with pytest.raises(NotFoundError):
                await api_get(log_id=uuid.uuid4(), db=AsyncMock())


# ─── Middleware 测试 ───


class TestAuditLogMiddleware:
    """审计中间件测试。"""

    def test_get_client_ip_direct(self) -> None:
        from app.core.audit_middleware import _get_client_ip
        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert _get_client_ip(request) == "10.0.0.1"

    def test_get_client_ip_forwarded(self) -> None:
        from app.core.audit_middleware import _get_client_ip
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18"}
        assert _get_client_ip(request) == "203.0.113.50"

    def test_skip_paths(self) -> None:
        from app.core.audit_middleware import _SKIP_PATHS
        assert "/api/v1/audit-logs" in _SKIP_PATHS
        assert "/api/v1/auth/login" in _SKIP_PATHS

    def test_path_pattern_extraction(self) -> None:
        from app.core.audit_middleware import _PATH_PATTERN
        m = _PATH_PATTERN.match("/api/v1/agents/abc-123")
        assert m is not None
        assert m.group(1) == "agents"
        assert m.group(2) == "abc-123"

    def test_path_pattern_collection(self) -> None:
        from app.core.audit_middleware import _PATH_PATTERN
        m = _PATH_PATTERN.match("/api/v1/audit-logs")
        assert m is not None
        assert m.group(1) == "audit-logs"
        assert m.group(2) is None
