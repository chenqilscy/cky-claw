"""进化建议 & 信号 API + Service + Schema 测试。

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
    EvolutionSignalCreate,
    EvolutionSignalListResponse,
    EvolutionSignalResponse,
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


# ---------------------------------------------------------------------------
# 信号 Schema 校验测试
# ---------------------------------------------------------------------------


def _make_signal(**overrides) -> MagicMock:
    """构造一个模拟 EvolutionSignalRecord ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "agent_name": "bot",
        "signal_type": "tool_performance",
        "tool_name": "search",
        "call_count": 10,
        "success_count": 8,
        "failure_count": 2,
        "avg_duration_ms": 150.5,
        "overall_score": None,
        "negative_rate": None,
        "metadata_": {},
        "created_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestEvolutionSignalSchemas:
    """信号 Pydantic Schema 校验。"""

    def test_create_valid_tool_performance(self) -> None:
        """有效的 tool_performance 信号。"""
        data = EvolutionSignalCreate(
            agent_name="bot",
            signal_type="tool_performance",
            tool_name="search",
            call_count=10,
            success_count=8,
            failure_count=2,
            avg_duration_ms=150.5,
        )
        assert data.signal_type == "tool_performance"
        assert data.tool_name == "search"
        assert data.call_count == 10

    def test_create_valid_evaluation(self) -> None:
        """有效的 evaluation 信号。"""
        data = EvolutionSignalCreate(
            agent_name="bot",
            signal_type="evaluation",
            overall_score=0.85,
            call_count=100,
        )
        assert data.overall_score == 0.85

    def test_create_valid_feedback(self) -> None:
        """有效的 feedback 信号。"""
        data = EvolutionSignalCreate(
            agent_name="bot",
            signal_type="feedback",
            call_count=50,
            success_count=40,
            failure_count=10,
            negative_rate=0.2,
        )
        assert data.negative_rate == 0.2

    def test_create_all_signal_types(self) -> None:
        """所有合法信号类型均可创建。"""
        for t in ("evaluation", "feedback", "tool_performance", "guardrail", "token_usage"):
            data = EvolutionSignalCreate(agent_name="bot", signal_type=t)
            assert data.signal_type == t

    def test_create_invalid_signal_type(self) -> None:
        """无效 signal_type 被拒绝。"""
        with pytest.raises(ValueError, match="signal_type 必须是"):
            EvolutionSignalCreate(agent_name="bot", signal_type="bogus")

    def test_create_agent_name_too_long(self) -> None:
        """agent_name 超过 64 字符被拒绝。"""
        with pytest.raises(ValueError):
            EvolutionSignalCreate(agent_name="a" * 65, signal_type="evaluation")

    def test_create_agent_name_empty(self) -> None:
        """agent_name 为空被拒绝。"""
        with pytest.raises(ValueError):
            EvolutionSignalCreate(agent_name="", signal_type="evaluation")

    def test_create_negative_call_count(self) -> None:
        """call_count 负数被拒绝。"""
        with pytest.raises(ValueError):
            EvolutionSignalCreate(
                agent_name="bot", signal_type="evaluation", call_count=-1
            )

    def test_create_overall_score_range(self) -> None:
        """overall_score 超出 [0,1] 范围被拒绝。"""
        with pytest.raises(ValueError):
            EvolutionSignalCreate(
                agent_name="bot", signal_type="evaluation", overall_score=1.5
            )
        with pytest.raises(ValueError):
            EvolutionSignalCreate(
                agent_name="bot", signal_type="evaluation", overall_score=-0.1
            )

    def test_create_defaults(self) -> None:
        """默认值正确。"""
        data = EvolutionSignalCreate(agent_name="bot", signal_type="evaluation")
        assert data.tool_name is None
        assert data.call_count == 0
        assert data.success_count == 0
        assert data.failure_count == 0
        assert data.avg_duration_ms == 0.0
        assert data.overall_score is None
        assert data.negative_rate is None
        assert data.metadata == {}

    def test_response_from_orm(self) -> None:
        """从 ORM 对象构造 EvolutionSignalResponse。"""
        mock = _make_signal()
        resp = EvolutionSignalResponse.model_validate(mock)
        assert resp.agent_name == "bot"
        assert resp.signal_type == "tool_performance"
        assert resp.metadata == {}


# ---------------------------------------------------------------------------
# 信号 Service 层测试（mock DB）
# ---------------------------------------------------------------------------


class TestEvolutionSignalService:
    """信号 Service 函数正确性。"""

    @pytest.mark.anyio()
    async def test_create_signal(self) -> None:
        """create_signal 写入并返回记录。"""
        mock_db = AsyncMock()

        from app.services.evolution import create_signal

        data = EvolutionSignalCreate(
            agent_name="bot",
            signal_type="tool_performance",
            tool_name="search",
            call_count=10,
            success_count=8,
            failure_count=2,
            avg_duration_ms=200.0,
        )
        record = await create_signal(mock_db, data)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.anyio()
    async def test_create_signals_batch(self) -> None:
        """create_signals_batch 批量写入。"""
        mock_db = AsyncMock()

        from app.services.evolution import create_signals_batch

        signals = [
            EvolutionSignalCreate(
                agent_name="bot",
                signal_type="tool_performance",
                tool_name=f"tool_{i}",
                call_count=i * 10,
            )
            for i in range(3)
        ]
        records = await create_signals_batch(mock_db, signals)
        assert mock_db.add.call_count == 3
        mock_db.commit.assert_awaited_once()
        assert len(records) == 3

    @pytest.mark.anyio()
    async def test_create_signals_batch_empty(self) -> None:
        """空批量写入不触发 commit（仅触发无害的 commit）。"""
        mock_db = AsyncMock()

        from app.services.evolution import create_signals_batch

        records = await create_signals_batch(mock_db, [])
        assert len(records) == 0

    @pytest.mark.anyio()
    async def test_list_signals(self) -> None:
        """list_signals 构建正确查询。"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 2
        mock_result.scalars.return_value.all.return_value = [
            _make_signal(),
            _make_signal(),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import list_signals

        rows, total = await list_signals(mock_db, limit=10, offset=0)
        assert total == 2
        assert len(rows) == 2

    @pytest.mark.anyio()
    async def test_list_signals_with_filters(self) -> None:
        """list_signals 使用筛选参数。"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import list_signals

        rows, total = await list_signals(
            mock_db,
            agent_name="bot",
            signal_type="evaluation",
            limit=5,
            offset=0,
        )
        assert total == 0
        assert len(rows) == 0
        # 验证两次 execute 调用（count + data）
        assert mock_db.execute.await_count == 2

    @pytest.mark.anyio()
    async def test_analyze_agent_no_signals(self) -> None:
        """analyze_agent 无信号时返回空列表。"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.evolution import analyze_agent

        proposals = await analyze_agent(mock_db, "bot")
        assert proposals == []

    @pytest.mark.anyio()
    async def test_analyze_agent_with_tool_signals(self) -> None:
        """analyze_agent 有 tool_performance 信号时调用 StrategyEngine。"""
        # 创建模拟信号记录
        signal_row = _make_signal(
            signal_type="tool_performance",
            agent_name="bot",
            tool_name="bad_tool",
            call_count=100,
            success_count=20,
            failure_count=80,
            avg_duration_ms=5000.0,
            overall_score=None,
            created_at=datetime.now(timezone.utc),
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # mock StrategyEngine.generate_proposals 返回空列表（策略可能不生成建议）
        with patch(
            "ckyclaw_framework.evolution.StrategyEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.generate_proposals.return_value = []
            MockEngine.return_value = engine_instance

            from app.services.evolution import analyze_agent

            proposals = await analyze_agent(mock_db, "bot")
            assert proposals == []
            engine_instance.generate_proposals.assert_called_once()

    @pytest.mark.anyio()
    async def test_analyze_agent_with_evaluation_signals(self) -> None:
        """analyze_agent 转换 evaluation 信号。"""
        signal_row = _make_signal(
            signal_type="evaluation",
            agent_name="bot",
            tool_name=None,
            call_count=50,
            overall_score=0.4,
            created_at=datetime.now(timezone.utc),
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("ckyclaw_framework.evolution.StrategyEngine") as MockEngine:
            engine_instance = MagicMock()
            engine_instance.generate_proposals.return_value = []
            MockEngine.return_value = engine_instance

            from app.services.evolution import analyze_agent

            proposals = await analyze_agent(mock_db, "bot")
            assert proposals == []
            # 验证信号已传入
            call_args = engine_instance.generate_proposals.call_args
            assert call_args[0][0] == "bot"
            assert len(call_args[0][1]) == 1

    @pytest.mark.anyio()
    async def test_analyze_agent_with_feedback_signals(self) -> None:
        """analyze_agent 转换 feedback 信号。"""
        signal_row = _make_signal(
            signal_type="feedback",
            agent_name="bot",
            call_count=100,
            success_count=30,
            failure_count=70,
            overall_score=None,
            created_at=datetime.now(timezone.utc),
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("ckyclaw_framework.evolution.StrategyEngine") as MockEngine:
            engine_instance = MagicMock()
            engine_instance.generate_proposals.return_value = []
            MockEngine.return_value = engine_instance

            from app.services.evolution import analyze_agent

            proposals = await analyze_agent(mock_db, "bot")
            assert proposals == []
            call_args = engine_instance.generate_proposals.call_args
            assert len(call_args[0][1]) == 1

    @pytest.mark.anyio()
    async def test_analyze_agent_skips_unknown_signal_type(self) -> None:
        """analyze_agent 忽略未知 signal_type 的记录。"""
        signal_row = _make_signal(
            signal_type="guardrail",
            agent_name="bot",
            created_at=datetime.now(timezone.utc),
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # guardrail 类型的信号目前不转换，signals 列表为空 → 早期返回
        from app.services.evolution import analyze_agent

        proposals = await analyze_agent(mock_db, "bot")
        assert proposals == []

    @pytest.mark.anyio()
    async def test_analyze_agent_persists_proposals(self) -> None:
        """analyze_agent 将策略引擎生成的建议持久化到 DB。"""
        signal_row = _make_signal(
            signal_type="tool_performance",
            agent_name="bot",
            tool_name="slow_tool",
            call_count=50,
            success_count=10,
            failure_count=40,
            avg_duration_ms=3000.0,
            created_at=datetime.now(timezone.utc),
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # mock 策略引擎返回一个建议
        mock_proposal = MagicMock()
        mock_proposal.agent_name = "bot"
        mock_proposal.proposal_type = MagicMock(value="tools")
        mock_proposal.trigger_reason = "工具失败率 80% 超过阈值"
        mock_proposal.current_value = None
        mock_proposal.proposed_value = {"action": "disable"}
        mock_proposal.confidence_score = 0.9
        mock_proposal.metadata = {}

        with patch("ckyclaw_framework.evolution.StrategyEngine") as MockEngine:
            engine_instance = MagicMock()
            engine_instance.generate_proposals.return_value = [mock_proposal]
            MockEngine.return_value = engine_instance

            from app.services.evolution import analyze_agent

            proposals = await analyze_agent(mock_db, "bot")
            assert len(proposals) == 1
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 信号 API 路由测试（mock service 层）
# ---------------------------------------------------------------------------


class TestEvolutionSignalAPI:
    """信号 API 端点测试。"""

    def test_create_signal(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals 创建信号。"""
        mock_record = _make_signal()
        with patch(
            "app.services.evolution.create_signal",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            resp = client.post(
                "/api/v1/evolution/signals",
                json={
                    "agent_name": "bot",
                    "signal_type": "tool_performance",
                    "tool_name": "search",
                    "call_count": 10,
                    "success_count": 8,
                    "failure_count": 2,
                    "avg_duration_ms": 150.5,
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["signal_type"] == "tool_performance"
        assert body["tool_name"] == "search"

    def test_create_signal_invalid_type(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals 非法类型返回 422。"""
        resp = client.post(
            "/api/v1/evolution/signals",
            json={
                "agent_name": "bot",
                "signal_type": "bogus",
            },
        )
        assert resp.status_code == 422

    def test_create_signal_minimal(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals 最小必填字段。"""
        mock_record = _make_signal(
            signal_type="evaluation",
            tool_name=None,
            call_count=0,
            success_count=0,
            failure_count=0,
            avg_duration_ms=0.0,
        )
        with patch(
            "app.services.evolution.create_signal",
            new_callable=AsyncMock,
            return_value=mock_record,
        ):
            resp = client.post(
                "/api/v1/evolution/signals",
                json={
                    "agent_name": "bot",
                    "signal_type": "evaluation",
                },
            )
        assert resp.status_code == 201

    def test_create_signals_batch(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals/batch 批量创建。"""
        mock_records = [_make_signal(), _make_signal()]
        with patch(
            "app.services.evolution.create_signals_batch",
            new_callable=AsyncMock,
            return_value=mock_records,
        ):
            resp = client.post(
                "/api/v1/evolution/signals/batch",
                json=[
                    {"agent_name": "bot", "signal_type": "tool_performance", "tool_name": "a"},
                    {"agent_name": "bot", "signal_type": "evaluation"},
                ],
            )
        assert resp.status_code == 201
        assert len(resp.json()) == 2

    def test_create_signals_batch_empty(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals/batch 空数组。"""
        with patch(
            "app.services.evolution.create_signals_batch",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.post("/api/v1/evolution/signals/batch", json=[])
        assert resp.status_code == 201
        assert resp.json() == []

    def test_create_signals_batch_invalid_item(self, client: TestClient) -> None:
        """POST /api/v1/evolution/signals/batch 含非法项返回 422。"""
        resp = client.post(
            "/api/v1/evolution/signals/batch",
            json=[
                {"agent_name": "bot", "signal_type": "evaluation"},
                {"agent_name": "bot", "signal_type": "invalid"},
            ],
        )
        assert resp.status_code == 422

    def test_list_signals(self, client: TestClient) -> None:
        """GET /api/v1/evolution/signals 返回列表。"""
        mock_record = _make_signal()
        with patch(
            "app.services.evolution.list_signals",
            new_callable=AsyncMock,
            return_value=([mock_record], 1),
        ):
            resp = client.get("/api/v1/evolution/signals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["data"]) == 1

    def test_list_signals_with_filters(self, client: TestClient) -> None:
        """GET /api/v1/evolution/signals 支持筛选参数。"""
        with patch(
            "app.services.evolution.list_signals",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_svc:
            resp = client.get(
                "/api/v1/evolution/signals",
                params={
                    "agent_name": "bot",
                    "signal_type": "tool_performance",
                    "limit": 5,
                    "offset": 10,
                },
            )
        assert resp.status_code == 200
        mock_svc.assert_awaited_once()
        call_kwargs = mock_svc.call_args
        assert call_kwargs.kwargs["agent_name"] == "bot"
        assert call_kwargs.kwargs["signal_type"] == "tool_performance"
        assert call_kwargs.kwargs["limit"] == 5
        assert call_kwargs.kwargs["offset"] == 10


# ---------------------------------------------------------------------------
# Analyze API 测试
# ---------------------------------------------------------------------------


class TestEvolutionAnalyzeAPI:
    """策略分析 API 端点测试。"""

    def test_analyze_agent(self, client: TestClient) -> None:
        """POST /api/v1/evolution/analyze/{agent_name} 返回分析结果。"""
        mock_proposal = _make_proposal()
        with patch(
            "app.services.evolution.analyze_agent",
            new_callable=AsyncMock,
            return_value=[mock_proposal],
        ):
            resp = client.post("/api/v1/evolution/analyze/bot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proposals_created"] == 1
        assert len(body["proposals"]) == 1

    def test_analyze_agent_no_proposals(self, client: TestClient) -> None:
        """POST /api/v1/evolution/analyze/{agent_name} 无建议时返回空。"""
        with patch(
            "app.services.evolution.analyze_agent",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.post("/api/v1/evolution/analyze/bot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proposals_created"] == 0
        assert body["proposals"] == []


# ---------------------------------------------------------------------------
# M8P2: 建议应用 & 策略引擎定时运行 测试
# ---------------------------------------------------------------------------


class TestApplyProposalToAgent:
    """apply_proposal_to_agent() 测试。"""

    @pytest.mark.anyio()
    async def test_apply_instructions_proposal(self) -> None:
        """将 instructions 类型建议应用到 Agent 配置。"""
        mock_db = AsyncMock()
        proposal_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        # mock proposal record
        proposal = _make_proposal(
            id=proposal_id,
            status="approved",
            proposal_type="instructions",
            proposed_value={"instructions": "优化后的指令"},
            agent_name="bot",
        )

        # mock agent record
        agent_mock = MagicMock()
        agent_mock.id = agent_id
        agent_mock.name = "bot"
        agent_mock.model = "gpt-4"
        agent_mock.instructions = "旧指令"

        # mock version record
        version_result = MagicMock()
        version_result.scalar.return_value = 2

        # Setup db.execute chain
        execute_results = [
            # get_proposal query
            MagicMock(scalar_one_or_none=MagicMock(return_value=proposal)),
            # agent query
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
            # max version query
            MagicMock(scalar=MagicMock(return_value=2)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        from app.services.evolution import apply_proposal_to_agent

        result = await apply_proposal_to_agent(mock_db, proposal_id)

        # 验证 Agent instructions 被修改
        assert agent_mock.instructions == "优化后的指令"
        # 验证 proposal 状态推进
        assert proposal.status == "applied"
        assert proposal.applied_at is not None
        mock_db.commit.assert_awaited()

    @pytest.mark.anyio()
    async def test_apply_model_proposal(self) -> None:
        """将 model 类型建议应用到 Agent。"""
        mock_db = AsyncMock()
        proposal_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        proposal = _make_proposal(
            id=proposal_id,
            status="approved",
            proposal_type="model",
            proposed_value={"model": "gpt-4o"},
        )

        agent_mock = MagicMock()
        agent_mock.id = agent_id
        agent_mock.name = "bot"
        agent_mock.model = "gpt-3.5-turbo"
        agent_mock.instructions = ""

        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=proposal)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
            MagicMock(scalar=MagicMock(return_value=0)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        from app.services.evolution import apply_proposal_to_agent

        await apply_proposal_to_agent(mock_db, proposal_id)
        assert agent_mock.model == "gpt-4o"
        assert proposal.status == "applied"

    @pytest.mark.anyio()
    async def test_apply_pending_auto_promotes_to_approved(self) -> None:
        """pending 状态建议可自动推进到 approved 再 applied（auto-apply 场景）。"""
        mock_db = AsyncMock()
        proposal_id = uuid.uuid4()

        proposal = _make_proposal(
            id=proposal_id,
            status="pending",
            proposal_type="instructions",
            proposed_value={"instructions": "新指令"},
        )

        agent_mock = MagicMock()
        agent_mock.id = uuid.uuid4()
        agent_mock.name = "bot"
        agent_mock.model = "gpt-4"
        agent_mock.instructions = "旧"

        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=proposal)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
            MagicMock(scalar=MagicMock(return_value=0)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        from app.services.evolution import apply_proposal_to_agent

        await apply_proposal_to_agent(mock_db, proposal_id)
        assert proposal.status == "applied"

    @pytest.mark.anyio()
    async def test_apply_rejected_raises(self) -> None:
        """rejected 状态不允许应用。"""
        mock_db = AsyncMock()
        proposal_id = uuid.uuid4()

        proposal = _make_proposal(id=proposal_id, status="rejected")
        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=proposal)
            )
        )

        from app.services.evolution import apply_proposal_to_agent

        with pytest.raises(ValidationError, match="只能应用 approved"):
            await apply_proposal_to_agent(mock_db, proposal_id)

    @pytest.mark.anyio()
    async def test_apply_agent_not_found(self) -> None:
        """目标 Agent 不存在时抛错。"""
        mock_db = AsyncMock()
        proposal_id = uuid.uuid4()

        proposal = _make_proposal(id=proposal_id, status="approved")
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=proposal)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        from app.services.evolution import apply_proposal_to_agent

        with pytest.raises(NotFoundError, match="不存在"):
            await apply_proposal_to_agent(mock_db, proposal_id)


class TestApplyValueToAgent:
    """_apply_value_to_agent() 单元测试。"""

    def test_instructions(self) -> None:
        """instructions 类型正确修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        mock_agent.instructions = "旧"
        _apply_value_to_agent(mock_agent, "instructions", {"instructions": "新指令"})
        assert mock_agent.instructions == "新指令"

    def test_model(self) -> None:
        """model 类型正确修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        mock_agent.model = "old"
        _apply_value_to_agent(mock_agent, "model", {"model": "gpt-4o"})
        assert mock_agent.model == "gpt-4o"

    def test_tools(self) -> None:
        """tools 类型正确修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        mock_agent.tool_names = ["old"]
        _apply_value_to_agent(mock_agent, "tools", {"tool_names": ["new1", "new2"]})
        assert mock_agent.tool_names == ["new1", "new2"]

    def test_guardrails(self) -> None:
        """guardrails 类型正确修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        mock_agent.guardrail_ids = []
        _apply_value_to_agent(mock_agent, "guardrails", {"guardrail_ids": ["g1"]})
        assert mock_agent.guardrail_ids == ["g1"]

    def test_empty_proposed_no_change(self) -> None:
        """空 proposed_value 不修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        mock_agent.instructions = "不变"
        _apply_value_to_agent(mock_agent, "instructions", {})
        assert mock_agent.instructions == "不变"

    def test_unknown_type_no_error(self) -> None:
        """未知 type 不报错也不修改。"""
        from app.services.evolution import _apply_value_to_agent

        mock_agent = MagicMock()
        _apply_value_to_agent(mock_agent, "unknown", {"foo": "bar"})


class TestSchedulerEvolutionAnalyze:
    """scheduler_engine 的 evolution_analyze 任务类型测试。"""

    @pytest.mark.anyio()
    async def test_evolution_analyze_no_proposals(self) -> None:
        """无建议时输出正确信息。"""
        mock_db = AsyncMock()
        agent_mock = MagicMock()
        agent_mock.name = "bot"

        task = MagicMock()
        task.agent_id = uuid.uuid4()
        task.task_type = "evolution_analyze"
        task.input_text = ""

        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=agent_mock)),
        ]
        mock_db.execute = AsyncMock(side_effect=execute_results)

        with patch(
            "app.services.evolution.analyze_agent",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from app.services.scheduler_engine import _execute_evolution_analyze

            result = await _execute_evolution_analyze(mock_db, task)
        assert "无新建议" in result

    @pytest.mark.anyio()
    async def test_evolution_analyze_with_auto_apply(self) -> None:
        """auto_apply=true 且置信度达标时自动应用。"""
        import json

        mock_db = AsyncMock()
        agent_mock = MagicMock()
        agent_mock.name = "bot"

        task = MagicMock()
        task.agent_id = uuid.uuid4()
        task.task_type = "evolution_analyze"
        task.input_text = json.dumps({"auto_apply": True, "min_confidence": 0.7})

        proposal1 = _make_proposal(
            id=uuid.uuid4(), confidence_score=0.9, status="pending"
        )
        proposal2 = _make_proposal(
            id=uuid.uuid4(), confidence_score=0.5, status="pending"
        )

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=agent_mock)
            )
        )

        with (
            patch(
                "app.services.evolution.analyze_agent",
                new_callable=AsyncMock,
                return_value=[proposal1, proposal2],
            ),
            patch(
                "app.services.evolution.apply_proposal_to_agent",
                new_callable=AsyncMock,
            ) as mock_apply,
        ):
            from app.services.scheduler_engine import _execute_evolution_analyze

            result = await _execute_evolution_analyze(mock_db, task)

        # 只有 confidence_score >= 0.7 的才被应用
        mock_apply.assert_awaited_once()
        assert "自动应用 1 条" in result
        assert "生成 2 条" in result

    @pytest.mark.anyio()
    async def test_evolution_analyze_auto_apply_disabled(self) -> None:
        """auto_apply=false 时不自动应用。"""
        import json

        mock_db = AsyncMock()
        agent_mock = MagicMock()
        agent_mock.name = "bot"

        task = MagicMock()
        task.agent_id = uuid.uuid4()
        task.task_type = "evolution_analyze"
        task.input_text = json.dumps({"auto_apply": False})

        proposal = _make_proposal(
            id=uuid.uuid4(), confidence_score=0.9, status="pending"
        )

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=agent_mock)
            )
        )

        with (
            patch(
                "app.services.evolution.analyze_agent",
                new_callable=AsyncMock,
                return_value=[proposal],
            ),
            patch(
                "app.services.evolution.apply_proposal_to_agent",
                new_callable=AsyncMock,
            ) as mock_apply,
        ):
            from app.services.scheduler_engine import _execute_evolution_analyze

            result = await _execute_evolution_analyze(mock_db, task)

        mock_apply.assert_not_awaited()
        assert "自动应用 0 条" in result


class TestScheduledTaskType:
    """task_type 字段相关测试。"""

    def test_schema_default_type(self) -> None:
        """ScheduledTaskCreate 默认 task_type 为 agent_run。"""
        from app.schemas.scheduled_task import ScheduledTaskCreate

        data = ScheduledTaskCreate(
            name="test",
            agent_id=uuid.uuid4(),
            cron_expr="0 0 * * *",
        )
        assert data.task_type == "agent_run"

    def test_schema_evolution_type(self) -> None:
        """task_type = evolution_analyze 有效。"""
        from app.schemas.scheduled_task import ScheduledTaskCreate

        data = ScheduledTaskCreate(
            name="进化分析",
            agent_id=uuid.uuid4(),
            cron_expr="0 */6 * * *",
            task_type="evolution_analyze",
        )
        assert data.task_type == "evolution_analyze"

    def test_schema_invalid_type(self) -> None:
        """无效 task_type 被拒绝。"""
        from app.schemas.scheduled_task import ScheduledTaskCreate

        with pytest.raises(ValueError):
            ScheduledTaskCreate(
                name="bad",
                agent_id=uuid.uuid4(),
                cron_expr="0 0 * * *",
                task_type="invalid_type",
            )

    def test_response_includes_task_type(self) -> None:
        """ScheduledTaskResponse 包含 task_type 字段。"""
        from app.schemas.scheduled_task import ScheduledTaskResponse

        now = datetime.now(timezone.utc)
        resp = ScheduledTaskResponse(
            id=uuid.uuid4(),
            name="test",
            description="",
            agent_id=uuid.uuid4(),
            cron_expr="0 0 * * *",
            input_text="",
            task_type="evolution_analyze",
            is_enabled=True,
            last_run_at=None,
            next_run_at=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.task_type == "evolution_analyze"
