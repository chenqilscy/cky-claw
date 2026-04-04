"""Workflow 工作流 — Backend 层测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.workflow import (
    EdgeSchema,
    StepSchema,
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowValidateResponse,
)
from app.services.workflow import validate_workflow_definition


# ── Schema 验证 ──────────────────────────────────────


class TestWorkflowSchemas:
    def test_create_minimal(self) -> None:
        data = WorkflowCreate(name="my-workflow")
        assert data.name == "my-workflow"
        assert data.steps == []
        assert data.edges == []
        assert data.timeout is None

    def test_create_full(self) -> None:
        data = WorkflowCreate(
            name="research-flow",
            description="Research workflow",
            steps=[
                StepSchema(id="s1", name="研究", type="agent", agent_name="researcher"),
                StepSchema(id="s2", name="总结", type="agent", agent_name="summarizer"),
            ],
            edges=[EdgeSchema(id="e1", source_step_id="s1", target_step_id="s2")],
            output_keys=["result"],
            timeout=300.0,
            guardrail_names=["content-safety"],
            metadata={"version": 1},
        )
        assert len(data.steps) == 2
        assert len(data.edges) == 1
        assert data.timeout == 300.0

    def test_create_invalid_name_uppercase(self) -> None:
        with pytest.raises(Exception):
            WorkflowCreate(name="INVALID!")

    def test_create_invalid_name_space(self) -> None:
        with pytest.raises(Exception):
            WorkflowCreate(name="has space")

    def test_update_partial(self) -> None:
        data = WorkflowUpdate(description="updated desc")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"description": "updated desc"}

    def test_update_steps(self) -> None:
        data = WorkflowUpdate(
            steps=[StepSchema(id="s1", name="step1", type="agent")],
        )
        dumped = data.model_dump(exclude_unset=True)
        assert "steps" in dumped
        assert len(dumped["steps"]) == 1

    def test_step_schema_defaults(self) -> None:
        s = StepSchema(id="s1")
        assert s.type == "agent"
        assert s.max_turns == 10
        assert s.max_iterations == 100
        assert s.parallel_step_ids == []

    def test_edge_schema(self) -> None:
        e = EdgeSchema(id="e1", source_step_id="a", target_step_id="b")
        assert e.source_step_id == "a"
        assert e.target_step_id == "b"

    def test_response_from_attributes(self) -> None:
        now = datetime.now(timezone.utc)
        wid = uuid.uuid4()
        obj = MagicMock()
        obj.id = wid
        obj.name = "test-wf"
        obj.description = "desc"
        obj.steps = [{"id": "s1", "name": "a", "type": "agent"}]
        obj.edges = []
        obj.input_schema = {}
        obj.output_keys = []
        obj.timeout = None
        obj.guardrail_names = []
        obj.metadata_ = {"key": "val"}
        obj.created_at = now
        obj.updated_at = now
        resp = WorkflowResponse.model_validate(obj, from_attributes=True)
        assert resp.id == wid
        assert resp.metadata == {"key": "val"}

    def test_validate_response(self) -> None:
        r = WorkflowValidateResponse(valid=True, errors=[])
        assert r.valid is True
        r2 = WorkflowValidateResponse(valid=False, errors=["err1"])
        assert not r2.valid

    def test_list_response(self) -> None:
        now = datetime.now(timezone.utc)
        wid = uuid.uuid4()
        resp = WorkflowListResponse(
            data=[
                WorkflowResponse(
                    id=wid, name="wf1", description="", steps=[], edges=[],
                    input_schema={}, output_keys=[], timeout=None,
                    guardrail_names=[], metadata={}, created_at=now, updated_at=now,
                )
            ],
            total=1,
        )
        assert resp.total == 1


# ── Validate 逻辑 ────────────────────────────────────


class TestWorkflowValidation:
    def test_valid_dag(self) -> None:
        steps = [{"id": "s1"}, {"id": "s2"}]
        edges = [{"source_step_id": "s1", "target_step_id": "s2"}]
        errors = validate_workflow_definition(steps, edges)
        assert errors == []

    def test_empty_steps(self) -> None:
        errors = validate_workflow_definition([], [])
        assert errors == []

    def test_duplicate_step_ids(self) -> None:
        steps = [{"id": "s1"}, {"id": "s1"}]
        errors = validate_workflow_definition(steps, [])
        assert any("重复" in e for e in errors)

    def test_edge_references_missing_step(self) -> None:
        steps = [{"id": "s1"}]
        edges = [{"source_step_id": "s1", "target_step_id": "s_missing"}]
        errors = validate_workflow_definition(steps, edges)
        assert any("不存在" in e for e in errors)

    def test_cycle_detection(self) -> None:
        steps = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [
            {"source_step_id": "a", "target_step_id": "b"},
            {"source_step_id": "b", "target_step_id": "c"},
            {"source_step_id": "c", "target_step_id": "a"},
        ]
        errors = validate_workflow_definition(steps, edges)
        assert any("循环" in e for e in errors)

    def test_self_loop(self) -> None:
        steps = [{"id": "x"}]
        edges = [{"source_step_id": "x", "target_step_id": "x"}]
        errors = validate_workflow_definition(steps, edges)
        assert any("循环" in e for e in errors)


# ── API 路由 ─────────────────────────────────────────

# We patch the service layer and use the TestClient.


def _make_app() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


class TestWorkflowAPI:
    """API 层测试（Mock service）。"""

    def test_create_workflow(self) -> None:
        wid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_record = MagicMock()
        mock_record.id = wid
        mock_record.name = "wf-api"
        mock_record.description = ""
        mock_record.steps = []
        mock_record.edges = []
        mock_record.input_schema = {}
        mock_record.output_keys = []
        mock_record.timeout = None
        mock_record.guardrail_names = []
        mock_record.metadata_ = {}
        mock_record.created_at = now
        mock_record.updated_at = now

        with patch("app.api.workflows.workflow_service.create_workflow", new_callable=AsyncMock, return_value=mock_record):
            client = _make_app()
            resp = client.post("/api/v1/workflows", json={"name": "wf-api", "steps": [], "edges": []})
            assert resp.status_code == 201
            body = resp.json()
            assert body["name"] == "wf-api"

    def test_list_workflows(self) -> None:
        with patch("app.api.workflows.workflow_service.list_workflows", new_callable=AsyncMock, return_value=([], 0)):
            client = _make_app()
            resp = client.get("/api/v1/workflows")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

    def test_get_workflow(self) -> None:
        wid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        mock_record = MagicMock()
        mock_record.id = wid
        mock_record.name = "existing"
        mock_record.description = ""
        mock_record.steps = []
        mock_record.edges = []
        mock_record.input_schema = {}
        mock_record.output_keys = []
        mock_record.timeout = None
        mock_record.guardrail_names = []
        mock_record.metadata_ = {}
        mock_record.created_at = now
        mock_record.updated_at = now

        with patch("app.api.workflows.workflow_service.get_workflow", new_callable=AsyncMock, return_value=mock_record):
            client = _make_app()
            resp = client.get(f"/api/v1/workflows/{wid}")
            assert resp.status_code == 200

    def test_delete_workflow(self) -> None:
        wid = uuid.uuid4()
        with patch("app.api.workflows.workflow_service.delete_workflow", new_callable=AsyncMock, return_value=None):
            client = _make_app()
            resp = client.delete(f"/api/v1/workflows/{wid}")
            assert resp.status_code == 204

    def test_validate_valid(self) -> None:
        client = _make_app()
        payload = {
            "name": "test-wf",
            "steps": [{"id": "s1", "name": "a", "type": "agent"}, {"id": "s2", "name": "b", "type": "agent"}],
            "edges": [{"id": "e1", "source_step_id": "s1", "target_step_id": "s2"}],
        }
        resp = client.post("/api/v1/workflows/validate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_cycle(self) -> None:
        client = _make_app()
        payload = {
            "name": "cycle-wf",
            "steps": [{"id": "a"}, {"id": "b"}],
            "edges": [
                {"id": "e1", "source_step_id": "a", "target_step_id": "b"},
                {"id": "e2", "source_step_id": "b", "target_step_id": "a"},
            ],
        }
        resp = client.post("/api/v1/workflows/validate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert any("循环" in e for e in body["errors"])

    def test_update_workflow(self) -> None:
        wid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        mock_record = MagicMock()
        mock_record.id = wid
        mock_record.name = "wf-update"
        mock_record.description = "updated"
        mock_record.steps = []
        mock_record.edges = []
        mock_record.input_schema = {}
        mock_record.output_keys = []
        mock_record.timeout = None
        mock_record.guardrail_names = []
        mock_record.metadata_ = {}
        mock_record.created_at = now
        mock_record.updated_at = now

        with patch("app.api.workflows.workflow_service.update_workflow", new_callable=AsyncMock, return_value=mock_record):
            client = _make_app()
            resp = client.put(f"/api/v1/workflows/{wid}", json={"description": "updated"})
            assert resp.status_code == 200
            assert resp.json()["description"] == "updated"
