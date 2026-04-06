"""进化建议 API + Service + Schema 测试。

使用 mock 方式测试，不依赖 PostgreSQL。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, ValidationError
from app.main import app
from app.schemas.evolution import (
    EvolutionProposalCreate,
    EvolutionProposalListResponse,
    EvolutionProposalResponse,
    EvolutionProposalUpdate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_proposal(**overrides) -> MagicMock:  # type: ignore[no-untyped-def]
    """构造一个模拟 EvolutionProposalRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "agent_name": "bot",
        "proposal_type": "instructions",
        "status": "pending",
        "trigger_reason": "评分 0.52 低于阈值 0.7",
        "current_value": {"instructions": "旧指令"},
        "proposed_value": {"instructions": "新指令"},
        "confidence_score": 0.8,
        "eval_before": None,
        "eval_after": None,
        "applied_at": None,
        "rolled_back_at": None,
        "metadata_": {"source": "auto"},
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema 校验测试
# ---------------------------------------------------------------------------


class TestEvolutionSchemas:
    """Pydantic Schema 校验。"""

    def test_create_valid(self) -> None:
        """有效创建请求。"""
        data = EvolutionProposalCreate(
            agent_name="bot",
            proposal_type="instructions",
            trigger_reason="分数低",
        )
        assert data.agent_name == "bot"
        assert data.proposal_type == "instructions"

    def test_create_invalid_type(self) -> None:
        """无效 proposal_type 被拒绝。"""
        with pytest.raises(ValueError, match="proposal_type 必须是"):
            EvolutionProposalCreate(
                agent_name="bot",
                proposal_type="invalid_type",
            )

    def test_create_all_types(self) -> None:
        """所有合法类型均可创建。"""
        for t in ("instructions", "tools", "guardrails", "model", "memory"):
            data = EvolutionProposalCreate(agent_name="bot", proposal_type=t)
            assert data.proposal_type == t

    def test_create_confidence_range(self) -> None:
        """置信度范围校验。"""
        data = EvolutionProposalCreate(
            agent_name="bot", proposal_type="tools", confidence_score=0.5
        )
        assert data.confidence_score == 0.5

        with pytest.raises(ValueError):
            EvolutionProposalCreate(
                agent_name="bot", proposal_type="tools", confidence_score=1.5
            )

        with pytest.raises(ValueError):
            EvolutionProposalCreate(
                agent_name="bot", proposal_type="tools", confidence_score=-0.1
            )

    def test_update_valid_status(self) -> None:
        """有效状态更新。"""
        data = EvolutionProposalUpdate(status="approved")
        assert data.status == "approved"

    def test_update_invalid_status(self) -> None:
        """无效状态被拒绝。"""
        with pytest.raises(ValueError, match="status 必须是"):
            EvolutionProposalUpdate(status="bogus")

    def test_response_from_orm(self) -> None:
        """从 ORM 对象构造 Response。"""
        mock = _make_proposal()
        resp = EvolutionProposalResponse.model_validate(mock)
        assert resp.agent_name == "bot"
        assert resp.metadata == {"source": "auto"}


# ---------------------------------------------------------------------------
# Service 层测试（mock DB）
# ---------------------------------------------------------------------------


class TestEvolutionService:
    """Service 函数正确性。"""

    @pytest.mark.anyio()
    async def test_list_proposals(self) -> None:
        """list_proposals 构建正确查询。"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_result.scalars.return_value.all.return_value = [_make_proposal()]
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import list_proposals

        rows, total = await list_proposals(mock_db, limit=10, offset=0)
        assert total == 1
        assert len(rows) == 1

    @pytest.mark.anyio()
    async def test_get_proposal_not_found(self) -> None:
        """不存在的 ID 抛出 NotFoundError。"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import get_proposal

        with pytest.raises(NotFoundError, match="不存在"):
            await get_proposal(mock_db, uuid.uuid4())

    @pytest.mark.anyio()
    async def test_create_proposal(self) -> None:
        """create_proposal 写入并返回记录。"""
        mock_db = AsyncMock()

        from app.services.evolution import create_proposal

        data = EvolutionProposalCreate(
            agent_name="bot",
            proposal_type="tools",
            trigger_reason="高失败率",
            confidence_score=0.7,
        )
        record = await create_proposal(mock_db, data)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.anyio()
    async def test_update_proposal_status_transition(self) -> None:
        """合法状态转换 pending → approved。"""
        existing = _make_proposal(status="pending")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        data = EvolutionProposalUpdate(status="approved")
        result = await update_proposal(mock_db, existing.id, data)
        assert result.status == "approved"

    @pytest.mark.anyio()
    async def test_update_proposal_invalid_transition(self) -> None:
        """非法状态转换 pending → applied 被拒绝。"""
        existing = _make_proposal(status="pending")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        with pytest.raises(ValidationError, match="不允许"):
            await update_proposal(
                mock_db, existing.id, EvolutionProposalUpdate(status="applied")
            )

    @pytest.mark.anyio()
    async def test_update_proposal_applied_sets_timestamp(self) -> None:
        """approved → applied 时自动设置 applied_at。"""
        existing = _make_proposal(status="approved")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        data = EvolutionProposalUpdate(status="applied", eval_before=0.6)
        result = await update_proposal(mock_db, existing.id, data)
        assert result.status == "applied"
        assert result.applied_at is not None
        assert result.eval_before == 0.6

    @pytest.mark.anyio()
    async def test_update_proposal_rolled_back(self) -> None:
        """applied → rolled_back 设置 rolled_back_at。"""
        existing = _make_proposal(status="applied")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        data = EvolutionProposalUpdate(status="rolled_back", eval_after=0.4)
        result = await update_proposal(mock_db, existing.id, data)
        assert result.status == "rolled_back"
        assert result.rolled_back_at is not None
        assert result.eval_after == 0.4

    @pytest.mark.anyio()
    async def test_delete_proposal(self) -> None:
        """delete_proposal 调用 db.delete + commit。"""
        existing = _make_proposal()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import delete_proposal

        await delete_proposal(mock_db, existing.id)
        mock_db.delete.assert_awaited_once_with(existing)
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# API 路由测试（mock service 层）
# ---------------------------------------------------------------------------


class TestEvolutionAPI:
    """Evolution API 端点测试。"""

    def test_list_proposals(self, client: TestClient) -> None:
        """GET /api/v1/evolution/proposals 返回列表。"""
        mock_record = _make_proposal()
        with patch(
            "app.services.evolution.list_proposals",
            new_callable=AsyncMock,
            return_value=([mock_record], 1),
        ):
            resp = client.get("/api/v1/evolution/proposals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["agent_name"] == "bot"

    def test_list_proposals_with_filters(self, client: TestClient) -> None:
        """GET /api/v1/evolution/proposals 支持筛选参数。"""
        with patch(
            "app.services.evolution.list_proposals",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_svc:
            resp = client.get(
                "/api/v1/evolution/proposals",
                params={
                    "agent_name": "bot",
                    "proposal_type": "tools",
                    "status": "pending",
                    "limit": 5,
                    "offset": 10,
                },
            )
        assert resp.status_code == 200
        mock_svc.assert_awaited_once()
        call_kwargs = mock_svc.call_args
        assert call_kwargs.kwargs["agent_name"] == "bot"
        assert call_kwargs.kwargs["proposal_type"] == "tools"
        assert call_kwargs.kwargs["status"] == "pending"
        assert call_kwargs.kwargs["limit"] == 5
        assert call_kwargs.kwargs["offset"] == 10

    def test_create_proposal(self, client: TestClient) -> None:
        """POST /api/v1/evolution/proposals 创建建议。"""
        mock_record = _make_proposal()
        with patch(
            "app.services.evolution.create_proposal",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            resp = client.post(
                "/api/v1/evolution/proposals",
                json={
                    "agent_name": "bot",
                    "proposal_type": "instructions",
                    "trigger_reason": "低分",
                    "confidence_score": 0.8,
                },
            )
        assert resp.status_code == 201
        assert resp.json()["proposal_type"] == "instructions"

    def test_create_proposal_invalid_type(self, client: TestClient) -> None:
        """POST /api/v1/evolution/proposals 非法类型返回 422。"""
        resp = client.post(
            "/api/v1/evolution/proposals",
            json={
                "agent_name": "bot",
                "proposal_type": "bogus",
            },
        )
        assert resp.status_code == 422

    def test_get_proposal(self, client: TestClient) -> None:
        """GET /api/v1/evolution/proposals/{id} 返回单条。"""
        mock_record = _make_proposal()
        with patch(
            "app.services.evolution.get_proposal",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            resp = client.get(f"/api/v1/evolution/proposals/{mock_record.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_get_proposal_not_found(self, client: TestClient) -> None:
        """GET /api/v1/evolution/proposals/{id} 不存在返回 404。"""
        with patch(
            "app.services.evolution.get_proposal",
            new_callable=AsyncMock,
            side_effect=NotFoundError("不存在"),
        ):
            resp = client.get(f"/api/v1/evolution/proposals/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_proposal(self, client: TestClient) -> None:
        """PATCH /api/v1/evolution/proposals/{id} 更新状态。"""
        mock_record = _make_proposal(status="approved")
        with patch(
            "app.services.evolution.update_proposal",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            resp = client.patch(
                f"/api/v1/evolution/proposals/{mock_record.id}",
                json={"status": "approved"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_update_proposal_invalid_transition(self, client: TestClient) -> None:
        """PATCH 非法状态转换返回 422。"""
        with patch(
            "app.services.evolution.update_proposal",
            new_callable=AsyncMock,
            side_effect=ValidationError("不允许"),
        ):
            resp = client.patch(
                f"/api/v1/evolution/proposals/{uuid.uuid4()}",
                json={"status": "applied"},
            )
        assert resp.status_code == 422

    def test_delete_proposal(self, client: TestClient) -> None:
        """DELETE /api/v1/evolution/proposals/{id} 返回 204。"""
        with patch(
            "app.services.evolution.delete_proposal",
            new_callable=AsyncMock,
        ):
            resp = client.delete(f"/api/v1/evolution/proposals/{uuid.uuid4()}")
        assert resp.status_code == 204

    def test_delete_proposal_not_found(self, client: TestClient) -> None:
        """DELETE 不存在返回 404。"""
        with patch(
            "app.services.evolution.delete_proposal",
            new_callable=AsyncMock,
            side_effect=NotFoundError("不存在"),
        ):
            resp = client.delete(f"/api/v1/evolution/proposals/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 状态转换矩阵测试
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    """进化建议状态机完整覆盖。"""

    @pytest.mark.anyio()
    async def test_pending_to_approved(self) -> None:
        """pending → approved 合法。"""
        existing = _make_proposal(status="pending")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        result = await update_proposal(
            mock_db, existing.id, EvolutionProposalUpdate(status="approved")
        )
        assert result.status == "approved"

    @pytest.mark.anyio()
    async def test_pending_to_rejected(self) -> None:
        """pending → rejected 合法。"""
        existing = _make_proposal(status="pending")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        result = await update_proposal(
            mock_db, existing.id, EvolutionProposalUpdate(status="rejected")
        )
        assert result.status == "rejected"

    @pytest.mark.anyio()
    async def test_approved_to_applied(self) -> None:
        """approved → applied 合法。"""
        existing = _make_proposal(status="approved")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        result = await update_proposal(
            mock_db, existing.id, EvolutionProposalUpdate(status="applied")
        )
        assert result.status == "applied"

    @pytest.mark.anyio()
    async def test_applied_to_rolled_back(self) -> None:
        """applied → rolled_back 合法。"""
        existing = _make_proposal(status="applied")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        result = await update_proposal(
            mock_db, existing.id, EvolutionProposalUpdate(status="rolled_back")
        )
        assert result.status == "rolled_back"

    @pytest.mark.anyio()
    async def test_rejected_cannot_transition(self) -> None:
        """rejected 状态不可转换。"""
        existing = _make_proposal(status="rejected")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        with pytest.raises(ValidationError, match="不允许"):
            await update_proposal(
                mock_db, existing.id, EvolutionProposalUpdate(status="approved")
            )

    @pytest.mark.anyio()
    async def test_rolled_back_cannot_transition(self) -> None:
        """rolled_back 状态不可转换。"""
        existing = _make_proposal(status="rolled_back")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        with pytest.raises(ValidationError, match="不允许"):
            await update_proposal(
                mock_db, existing.id, EvolutionProposalUpdate(status="pending")
            )

    @pytest.mark.anyio()
    async def test_pending_to_applied_blocked(self) -> None:
        """pending 不能直接跳到 applied。"""
        existing = _make_proposal(status="pending")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        with pytest.raises(ValidationError, match="不允许"):
            await update_proposal(
                mock_db, existing.id, EvolutionProposalUpdate(status="applied")
            )

    @pytest.mark.anyio()
    async def test_approved_to_rejected_blocked(self) -> None:
        """approved 不能回退到 rejected。"""
        existing = _make_proposal(status="approved")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import update_proposal

        with pytest.raises(ValidationError, match="不允许"):
            await update_proposal(
                mock_db, existing.id, EvolutionProposalUpdate(status="rejected")
            )
