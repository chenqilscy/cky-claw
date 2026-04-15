"""Team 团队 — Backend 层测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.team import (
    TeamConfigCreate,
    TeamConfigListResponse,
    TeamConfigResponse,
    TeamConfigUpdate,
)

# ── Schema 验证 ──────────────────────────────────────


class TestTeamSchemas:
    def test_create_minimal(self) -> None:
        data = TeamConfigCreate(name="my-team")
        assert data.name == "my-team"
        assert data.protocol == "SEQUENTIAL"
        assert data.member_agent_ids == []
        assert data.coordinator_agent_id is None

    def test_create_full(self) -> None:
        data = TeamConfigCreate(
            name="research-team",
            description="Research team",
            protocol="COORDINATOR",
            member_agent_ids=["agent-1", "agent-2"],
            coordinator_agent_id="coordinator-agent",
            config={"max_rounds": 5},
        )
        assert data.protocol == "COORDINATOR"
        assert len(data.member_agent_ids) == 2
        assert data.config["max_rounds"] == 5

    def test_update_partial(self) -> None:
        data = TeamConfigUpdate(description="Updated")
        dumped = data.model_dump(exclude_unset=True)
        assert "description" in dumped
        assert "name" not in dumped
        assert "protocol" not in dumped

    def test_response_from_dict(self) -> None:
        now = datetime.now(UTC)
        resp = TeamConfigResponse(
            id=uuid.uuid4(),
            name="test",
            description="desc",
            protocol="PARALLEL",
            member_agent_ids=["a1"],
            coordinator_agent_id=None,
            config={},
            created_at=now,
            updated_at=now,
        )
        assert resp.protocol == "PARALLEL"
        assert resp.member_agent_ids == ["a1"]

    def test_list_response(self) -> None:
        resp = TeamConfigListResponse(data=[], total=0)
        assert resp.total == 0


# ── Service 层测试 ─────────────────────────────────


class TestTeamService:
    @pytest.mark.asyncio
    async def test_create_team(self) -> None:
        from app.services.team import create_team

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        data = TeamConfigCreate(
            name="test-team",
            protocol="SEQUENTIAL",
            member_agent_ids=["agent-1"],
        )
        await create_team(mock_db, data)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_team_invalid_protocol(self) -> None:
        from app.services.team import create_team

        mock_db = AsyncMock()
        data = TeamConfigCreate(name="bad-team", protocol="INVALID")
        with pytest.raises(ValueError, match="无效协议"):
            await create_team(mock_db, data)

    @pytest.mark.asyncio
    async def test_create_team_coordinator_requires_id(self) -> None:
        from app.services.team import create_team

        mock_db = AsyncMock()
        data = TeamConfigCreate(name="coord-team", protocol="COORDINATOR")
        with pytest.raises(ValueError, match="coordinator_agent_id"):
            await create_team(mock_db, data)

    @pytest.mark.asyncio
    async def test_get_team_not_found(self) -> None:
        from app.core.exceptions import NotFoundError
        from app.services.team import get_team

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await get_team(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_teams(self) -> None:
        from app.services.team import list_teams

        mock_db = AsyncMock()
        # count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        # data query
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        rows, total = await list_teams(mock_db, limit=10, offset=0)
        assert total == 0
        assert rows == []

    @pytest.mark.asyncio
    async def test_list_teams_with_search(self) -> None:
        from app.services.team import list_teams

        mock_db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = ["mock_record"]
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        rows, total = await list_teams(mock_db, search="research")
        assert total == 1
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_delete_team(self) -> None:
        from app.services.team import delete_team

        mock_db = AsyncMock()
        mock_record = MagicMock()
        mock_record.is_deleted = False
        mock_record.deleted_at = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        await delete_team(mock_db, uuid.uuid4())
        assert mock_record.is_deleted is True
        assert mock_record.deleted_at is not None
        mock_db.commit.assert_called_once()


# ── API 路由测试 ──────────────────────────────────


class TestTeamAPI:
    @pytest.fixture
    def client(self) -> TestClient:
        from app.main import app
        return TestClient(app)

    def test_create_team(self, client: TestClient) -> None:
        with patch("app.services.team.create_team", new_callable=AsyncMock) as mock_create:
            now = datetime.now(UTC)
            mock_record = MagicMock()
            mock_record.configure_mock(
                id=uuid.uuid4(),
                name="api-team",
                description="",
                protocol="SEQUENTIAL",
                member_agent_ids=["a1"],
                coordinator_agent_id=None,
                config={},
                created_at=now,
                updated_at=now,
            )
            mock_create.return_value = mock_record
            resp = client.post("/api/v1/teams", json={
                "name": "api-team",
                "member_agent_ids": ["a1"],
            })
            assert resp.status_code == 201
            body = resp.json()
            assert body["name"] == "api-team"
            assert body["protocol"] == "SEQUENTIAL"

    def test_list_teams(self, client: TestClient) -> None:
        with patch("app.services.team.list_teams", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            resp = client.get("/api/v1/teams")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 0
            assert body["data"] == []

    def test_get_team(self, client: TestClient) -> None:
        tid = uuid.uuid4()
        with patch("app.services.team.get_team", new_callable=AsyncMock) as mock_get:
            now = datetime.now(UTC)
            mock_record = MagicMock()
            mock_record.configure_mock(
                id=tid,
                name="found",
                description="desc",
                protocol="PARALLEL",
                member_agent_ids=[],
                coordinator_agent_id=None,
                config={},
                created_at=now,
                updated_at=now,
            )
            mock_get.return_value = mock_record
            resp = client.get(f"/api/v1/teams/{tid}")
            assert resp.status_code == 200
            assert resp.json()["name"] == "found"

    def test_update_team(self, client: TestClient) -> None:
        tid = uuid.uuid4()
        with patch("app.services.team.update_team", new_callable=AsyncMock) as mock_update:
            now = datetime.now(UTC)
            mock_record = MagicMock()
            mock_record.configure_mock(
                id=tid,
                name="updated",
                description="new desc",
                protocol="PARALLEL",
                member_agent_ids=["a1", "a2"],
                coordinator_agent_id=None,
                config={},
                created_at=now,
                updated_at=now,
            )
            mock_update.return_value = mock_record
            resp = client.put(f"/api/v1/teams/{tid}", json={"name": "updated"})
            assert resp.status_code == 200
            assert resp.json()["name"] == "updated"

    def test_delete_team(self, client: TestClient) -> None:
        tid = uuid.uuid4()
        with patch("app.services.team.delete_team", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = None
            resp = client.delete(f"/api/v1/teams/{tid}")
            assert resp.status_code == 204

    def test_get_team_not_found(self, client: TestClient) -> None:
        tid = uuid.uuid4()
        from app.core.exceptions import NotFoundError
        with patch("app.services.team.get_team", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = NotFoundError(f"团队 '{tid}' 不存在")
            resp = client.get(f"/api/v1/teams/{tid}")
            assert resp.status_code == 404
