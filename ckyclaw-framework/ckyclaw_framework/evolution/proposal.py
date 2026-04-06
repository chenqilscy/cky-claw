"""进化建议（Evolution Proposal）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ProposalType(str, Enum):
    """建议类型。"""

    INSTRUCTIONS = "instructions"
    """优化 Agent Instructions（Prompt）。"""

    TOOLS = "tools"
    """调整工具配置（启用/禁用/排序）。"""

    GUARDRAILS = "guardrails"
    """调整 Guardrail 阈值或规则。"""

    MODEL = "model"
    """切换模型或调整模型参数。"""

    MEMORY = "memory"
    """合并/清理记忆条目。"""


class ProposalStatus(str, Enum):
    """建议状态。"""

    PENDING = "pending"
    """待审批。"""

    APPROVED = "approved"
    """已批准，等待应用。"""

    REJECTED = "rejected"
    """已拒绝。"""

    APPLIED = "applied"
    """已应用。"""

    ROLLED_BACK = "rolled_back"
    """已回滚（应用后效果退化）。"""


@dataclass
class EvolutionProposal:
    """进化优化建议。

    代表一条具体的 Agent 优化建议，包含当前值、建议值、
    触发原因、置信度和状态跟踪。
    """

    agent_name: str
    """目标 Agent 名称。"""

    proposal_type: ProposalType
    """建议类型。"""

    trigger_reason: str
    """触发原因描述（如"平均评分 0.52 低于阈值 0.7"）。"""

    current_value: Any = None
    """当前配置值（dict/str/list，取决于 proposal_type）。"""

    proposed_value: Any = None
    """建议的新配置值。"""

    id: str = field(default_factory=lambda: str(uuid4()))
    """建议 ID。"""

    status: ProposalStatus = ProposalStatus.PENDING
    """当前状态。"""

    confidence_score: float = 0.0
    """置信度（0.0~1.0）。越高表示优化效果越确信。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """创建时间。"""

    applied_at: datetime | None = None
    """应用时间。"""

    rolled_back_at: datetime | None = None
    """回滚时间。"""

    eval_before: float | None = None
    """应用前的平均评分。"""

    eval_after: float | None = None
    """应用后的平均评分。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据（如信号详情、LLM 推理过程等）。"""

    def approve(self) -> None:
        """批准建议。"""
        if self.status != ProposalStatus.PENDING:
            msg = f"只能批准 PENDING 状态的建议，当前状态: {self.status.value}"
            raise ValueError(msg)
        self.status = ProposalStatus.APPROVED

    def reject(self) -> None:
        """拒绝建议。"""
        if self.status != ProposalStatus.PENDING:
            msg = f"只能拒绝 PENDING 状态的建议，当前状态: {self.status.value}"
            raise ValueError(msg)
        self.status = ProposalStatus.REJECTED

    def mark_applied(self, eval_before: float | None = None) -> None:
        """标记建议已应用。

        Args:
            eval_before: 应用前的评分基线。
        """
        if self.status != ProposalStatus.APPROVED:
            msg = f"只能应用 APPROVED 状态的建议，当前状态: {self.status.value}"
            raise ValueError(msg)
        self.status = ProposalStatus.APPLIED
        self.applied_at = datetime.now(timezone.utc)
        self.eval_before = eval_before

    def mark_rolled_back(self, eval_after: float | None = None) -> None:
        """标记建议已回滚。

        Args:
            eval_after: 应用后的评分（触发回滚的依据）。
        """
        if self.status != ProposalStatus.APPLIED:
            msg = f"只能回滚 APPLIED 状态的建议，当前状态: {self.status.value}"
            raise ValueError(msg)
        self.status = ProposalStatus.ROLLED_BACK
        self.rolled_back_at = datetime.now(timezone.utc)
        self.eval_after = eval_after

    def update_eval_after(self, eval_after: float) -> None:
        """更新应用后的评分。

        Args:
            eval_after: 应用后的新评分。
        """
        self.eval_after = eval_after
