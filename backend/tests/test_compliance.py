"""Compliance 合规框架全栈测试 — Schema / API / Service / Router。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.compliance import (
    ClassificationLabelCreate,
    ClassificationLabelListResponse,
    ClassificationLabelResponse,
    ComplianceDashboardResponse,
    ControlPointCreate,
    ControlPointListResponse,
    ControlPointResponse,
    ControlPointUpdate,
    ErasureRequestCreate,
    ErasureRequestListResponse,
    ErasureRequestResponse,
    RetentionPolicyCreate,
    RetentionPolicyListResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)

now = datetime.now(timezone.utc)
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_label(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "resource_type": "trace",
        "resource_id": "abc-123",
        "classification": "pii",
        "auto_detected": False,
        "reason": "contains email",
        "is_deleted": False,
        "created_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_policy(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "resource_type": "trace",
        "classification": "sensitive",
        "retention_days": 90,
        "status": "active",
        "last_executed_at": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_erasure(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "requester_user_id": USER_ID,
        "target_user_id": uuid.uuid4(),
        "status": "pending",
        "scanned_resources": 0,
        "deleted_resources": 0,
        "report": None,
        "completed_at": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


def _make_control(**overrides: object) -> MagicMock:
    d: dict[str, object] = {
        "id": uuid.uuid4(),
        "control_id": "CC6.1",
        "category": "Security",
        "description": "Logical access controls",
        "implementation": "RBAC + JWT",
        "evidence_links": None,
        "is_satisfied": True,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    d.update(overrides)
    m = MagicMock()
    for k, v in d.items():
        setattr(m, k, v)
    return m


# ──────────────────────────────────────────────
# Schema 测试
# ──────────────────────────────────────────────

class TestComplianceSchemas:
    def test_label_create_valid(self) -> None:
        lc = ClassificationLabelCreate(resource_type="trace", resource_id="abc", classification="pii")
        assert lc.classification == "pii"

    def test_label_create_invalid_classification(self) -> None:
        with pytest.raises(ValidationError):
            ClassificationLabelCreate(resource_type="trace", resource_id="abc", classification="unknown")

    def test_label_response(self) -> None:
        label = _make_label()
        resp = ClassificationLabelResponse.model_validate(label)
        assert resp.resource_type == "trace"

    def test_policy_create(self) -> None:
        pc = RetentionPolicyCreate(resource_type="session", classification="internal", retention_days=30)
        assert pc.retention_days == 30

    def test_policy_create_invalid_days(self) -> None:
        with pytest.raises(ValidationError):
            RetentionPolicyCreate(resource_type="session", classification="internal", retention_days=0)

    def test_policy_response(self) -> None:
        p = _make_policy()
        resp = RetentionPolicyResponse.model_validate(p)
        assert resp.status == "active"

    def test_erasure_create(self) -> None:
        ec = ErasureRequestCreate(target_user_id=uuid.uuid4())
        assert ec.target_user_id is not None

    def test_erasure_response(self) -> None:
        e = _make_erasure()
        resp = ErasureRequestResponse.model_validate(e)
        assert resp.status == "pending"

    def test_control_create(self) -> None:
        cc = ControlPointCreate(control_id="CC6.1", category="Security", description="test")
        assert cc.control_id == "CC6.1"

    def test_control_update(self) -> None:
        cu = ControlPointUpdate(is_satisfied=True)
        assert cu.is_satisfied is True

    def test_control_response(self) -> None:
        cp = _make_control()
        resp = ControlPointResponse.model_validate(cp)
        assert resp.is_satisfied is True

    def test_dashboard_response(self) -> None:
        d = ComplianceDashboardResponse(
            total_control_points=10, satisfied_control_points=7,
            satisfaction_rate=0.7, active_retention_policies=3,
            pending_erasure_requests=1, classification_summary={"pii": 5},
        )
        assert d.satisfaction_rate == 0.7


# ──────────────────────────────────────────────
# API 测试
# ──────────────────────────────────────────────

class TestComplianceAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_get_dashboard(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.get_dashboard = AsyncMock(return_value={
            "total_control_points": 10, "satisfied_control_points": 7,
            "satisfaction_rate": 0.7, "active_retention_policies": 3,
            "pending_erasure_requests": 1, "classification_summary": {"pii": 5},
        })
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/compliance/dashboard")
        assert resp.status_code == 200
        assert resp.json()["satisfaction_rate"] == 0.7

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_create_label(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        label = _make_label()
        mock_svc.create_label = AsyncMock(return_value=label)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/compliance/labels", json={
            "resource_type": "trace", "resource_id": "abc", "classification": "pii",
        })
        assert resp.status_code == 201

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_list_labels(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.list_labels = AsyncMock(return_value=([_make_label()], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/compliance/labels")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_create_retention_policy(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        p = _make_policy()
        mock_svc.create_retention_policy = AsyncMock(return_value=p)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/compliance/retention-policies", json={
            "resource_type": "trace", "classification": "sensitive", "retention_days": 90,
        })
        assert resp.status_code == 201

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_list_retention_policies(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.list_retention_policies = AsyncMock(return_value=([_make_policy()], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/compliance/retention-policies")
        assert resp.status_code == 200

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_update_retention_policy(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        p = _make_policy(retention_days=180)
        mock_svc.update_retention_policy = AsyncMock(return_value=p)
        mock_db.return_value = AsyncMock()
        pid = uuid.uuid4()
        resp = self.client.put(f"/api/v1/compliance/retention-policies/{pid}", json={"retention_days": 180})
        assert resp.status_code == 200

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_create_erasure_request(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        e = _make_erasure()
        mock_svc.create_erasure_request = AsyncMock(return_value=e)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/compliance/erasure-requests", json={
            "target_user_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 201

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_list_erasure_requests(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.list_erasure_requests = AsyncMock(return_value=([_make_erasure()], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/compliance/erasure-requests")
        assert resp.status_code == 200

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_create_control_point(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        cp = _make_control()
        mock_svc.create_control_point = AsyncMock(return_value=cp)
        mock_db.return_value = AsyncMock()
        resp = self.client.post("/api/v1/compliance/control-points", json={
            "control_id": "CC6.1", "category": "Security", "description": "test",
        })
        assert resp.status_code == 201

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_list_control_points(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        mock_svc.list_control_points = AsyncMock(return_value=([_make_control()], 1))
        mock_db.return_value = AsyncMock()
        resp = self.client.get("/api/v1/compliance/control-points")
        assert resp.status_code == 200

    @patch("app.api.compliance.comp_svc")
    @patch("app.api.compliance.get_db")
    def test_update_control_point(self, mock_db: MagicMock, mock_svc: MagicMock) -> None:
        cp = _make_control(is_satisfied=True)
        mock_svc.update_control_point = AsyncMock(return_value=cp)
        mock_db.return_value = AsyncMock()
        pid = uuid.uuid4()
        resp = self.client.put(f"/api/v1/compliance/control-points/{pid}", json={"is_satisfied": True})
        assert resp.status_code == 200


# ──────────────────────────────────────────────
# Service 测试
# ──────────────────────────────────────────────

class TestComplianceService:
    @pytest.fixture()
    def db(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_erasure_duplicate_raises(self, db: AsyncMock) -> None:
        from app.core.exceptions import ConflictError
        from app.services.compliance import create_erasure_request

        existing = _make_erasure()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(ConflictError, match="已有待处理"):
            await create_erasure_request(db, USER_ID, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_policy_not_found(self, db: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.compliance import update_retention_policy

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(NotFoundError):
            await update_retention_policy(db, uuid.uuid4(), retention_days=30)

    @pytest.mark.asyncio
    async def test_update_control_not_found(self, db: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.compliance import update_control_point

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(NotFoundError):
            await update_control_point(db, uuid.uuid4(), is_satisfied=True)

    @pytest.mark.asyncio
    async def test_process_erasure_not_found(self, db: AsyncMock) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.compliance import process_erasure_request

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(NotFoundError):
            await process_erasure_request(db, uuid.uuid4(), 0, 0)


# ──────────────────────────────────────────────
# Router 测试
# ──────────────────────────────────────────────

class TestComplianceRouter:
    def test_router_has_expected_routes(self) -> None:
        from app.api.compliance import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/compliance/dashboard" in paths
        assert "/api/v1/compliance/labels" in paths
        assert "/api/v1/compliance/retention-policies" in paths
        assert "/api/v1/compliance/erasure-requests" in paths
        assert "/api/v1/compliance/control-points" in paths

    def test_router_registered_in_app(self) -> None:
        from app.main import app
        paths = [r.path for r in app.routes]
        assert "/api/v1/compliance/dashboard" in paths
