"""EvolutionProposal 测试。"""

from __future__ import annotations

import pytest

from kasaya.evolution.proposal import (
    EvolutionProposal,
    ProposalStatus,
    ProposalType,
)


class TestProposalType:
    """ProposalType 枚举测试。"""

    def test_values(self) -> None:
        """枚举值完整。"""
        assert ProposalType.INSTRUCTIONS.value == "instructions"
        assert ProposalType.TOOLS.value == "tools"
        assert ProposalType.GUARDRAILS.value == "guardrails"
        assert ProposalType.MODEL.value == "model"
        assert ProposalType.MEMORY.value == "memory"


class TestProposalStatus:
    """ProposalStatus 枚举测试。"""

    def test_values(self) -> None:
        """枚举值完整。"""
        assert ProposalStatus.PENDING.value == "pending"
        assert ProposalStatus.APPROVED.value == "approved"
        assert ProposalStatus.REJECTED.value == "rejected"
        assert ProposalStatus.APPLIED.value == "applied"
        assert ProposalStatus.ROLLED_BACK.value == "rolled_back"


class TestEvolutionProposal:
    """EvolutionProposal 测试。"""

    def _make_proposal(self, **overrides: object) -> EvolutionProposal:
        """构造测试 Proposal。"""
        defaults = {
            "agent_name": "bot",
            "proposal_type": ProposalType.INSTRUCTIONS,
            "trigger_reason": "评分低于阈值",
        }
        defaults.update(overrides)  # type: ignore[arg-type]
        return EvolutionProposal(**defaults)  # type: ignore[arg-type]

    def test_defaults(self) -> None:
        """默认值正确。"""
        p = self._make_proposal()
        assert p.agent_name == "bot"
        assert p.proposal_type == ProposalType.INSTRUCTIONS
        assert p.status == ProposalStatus.PENDING
        assert p.confidence_score == 0.0
        assert p.applied_at is None
        assert p.rolled_back_at is None
        assert p.eval_before is None
        assert p.eval_after is None
        assert p.id  # UUID 已生成

    def test_approve(self) -> None:
        """批准建议。"""
        p = self._make_proposal()
        p.approve()
        assert p.status == ProposalStatus.APPROVED

    def test_approve_non_pending_raises(self) -> None:
        """非 PENDING 状态批准报错。"""
        p = self._make_proposal()
        p.approve()
        with pytest.raises(ValueError, match="只能批准 PENDING"):
            p.approve()

    def test_reject(self) -> None:
        """拒绝建议。"""
        p = self._make_proposal()
        p.reject()
        assert p.status == ProposalStatus.REJECTED

    def test_reject_non_pending_raises(self) -> None:
        """非 PENDING 状态拒绝报错。"""
        p = self._make_proposal()
        p.reject()
        with pytest.raises(ValueError, match="只能拒绝 PENDING"):
            p.reject()

    def test_mark_applied(self) -> None:
        """标记已应用。"""
        p = self._make_proposal()
        p.approve()
        p.mark_applied(eval_before=0.65)
        assert p.status == ProposalStatus.APPLIED
        assert p.applied_at is not None
        assert p.eval_before == 0.65

    def test_mark_applied_non_approved_raises(self) -> None:
        """非 APPROVED 状态应用报错。"""
        p = self._make_proposal()
        with pytest.raises(ValueError, match="只能应用 APPROVED"):
            p.mark_applied()

    def test_mark_rolled_back(self) -> None:
        """标记已回滚。"""
        p = self._make_proposal()
        p.approve()
        p.mark_applied()
        p.mark_rolled_back(eval_after=0.55)
        assert p.status == ProposalStatus.ROLLED_BACK
        assert p.rolled_back_at is not None
        assert p.eval_after == 0.55

    def test_mark_rolled_back_non_applied_raises(self) -> None:
        """非 APPLIED 状态回滚报错。"""
        p = self._make_proposal()
        with pytest.raises(ValueError, match="只能回滚 APPLIED"):
            p.mark_rolled_back()

    def test_update_eval_after(self) -> None:
        """更新应用后评分。"""
        p = self._make_proposal()
        p.update_eval_after(0.82)
        assert p.eval_after == 0.82

    def test_full_lifecycle(self) -> None:
        """完整生命周期：pending → approved → applied → rolled_back。"""
        p = self._make_proposal(confidence_score=0.7)
        assert p.status == ProposalStatus.PENDING

        p.approve()
        assert p.status == ProposalStatus.APPROVED

        p.mark_applied(eval_before=0.65)
        assert p.status == ProposalStatus.APPLIED

        p.update_eval_after(0.50)
        assert p.eval_after == 0.50

        p.mark_rolled_back(eval_after=0.50)
        assert p.status == ProposalStatus.ROLLED_BACK

    def test_metadata(self) -> None:
        """元数据存储正常。"""
        p = self._make_proposal(metadata={"key": "value"})
        assert p.metadata == {"key": "value"}
