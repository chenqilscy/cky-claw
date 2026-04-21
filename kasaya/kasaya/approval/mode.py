"""Approval Mode 枚举与决策结果。"""

from __future__ import annotations

from enum import StrEnum


class ApprovalMode(StrEnum):
    """Agent 审批模式。"""

    SUGGEST = "suggest"
    """每次工具调用都需要审批确认。"""

    AUTO_EDIT = "auto-edit"
    """低风险操作自动执行，高风险需审批。"""

    FULL_AUTO = "full-auto"
    """完全自动执行，不需要审批。"""


class ApprovalDecision(StrEnum):
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


# ── auto-edit 风险分级 ──

# 安全操作关键词（工具名或参数模式匹配即视为安全）
SAFE_TOOL_PREFIXES: frozenset[str] = frozenset({
    "get_", "list_", "read_", "fetch_", "search_", "query_",
    "show_", "view_", "describe_", "count_", "check_",
})

# 高风险操作关键词（工具名匹配即视为高风险）
RISKY_TOOL_PREFIXES: frozenset[str] = frozenset({
    "delete_", "remove_", "drop_", "destroy_", "purge_",
    "execute_", "run_", "eval_", "exec_",
    "deploy_", "publish_", "push_",
    "send_", "post_", "submit_",
})


def classify_tool_risk(tool_name: str, *, approval_required: bool = False) -> bool:
    """判断工具是否需要审批（auto-edit 模式下）。

    Returns:
        True = 需要审批（高风险），False = 安全自动执行。
    """
    # 工具本身标记了 approval_required
    if approval_required:
        return True

    name_lower = tool_name.lower()

    # 匹配安全前缀 → 自动执行
    for prefix in SAFE_TOOL_PREFIXES:
        if name_lower.startswith(prefix):
            return False

    # 匹配高风险前缀 → 需要审批
    for prefix in RISKY_TOOL_PREFIXES:
        if name_lower.startswith(prefix):
            return True

    # 默认：未知工具视为高风险，需要审批
    return True
