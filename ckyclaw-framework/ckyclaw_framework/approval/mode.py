"""Approval Mode 枚举与决策结果。"""

from __future__ import annotations

from enum import Enum


class ApprovalMode(str, Enum):
    """Agent 审批模式。"""

    SUGGEST = "suggest"
    """每次工具调用都需要审批确认。"""

    AUTO_EDIT = "auto-edit"
    """低风险操作自动执行，高风险需审批。"""

    FULL_AUTO = "full-auto"
    """完全自动执行，不需要审批。"""


class ApprovalDecision(str, Enum):
    """审批决策结果。"""

    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalRejectedError(Exception):
    """审批被拒绝时抛出的异常。"""

    def __init__(self, tool_name: str, reason: str = "") -> None:
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool call '{tool_name}' was rejected: {reason}")
