"""Approval mode + classify_tool_risk 单元测试。"""

from __future__ import annotations

from ckyclaw_framework.approval.mode import (
    ApprovalDecision,
    ApprovalMode,
    ApprovalRejectedError,
    classify_tool_risk,
)


class TestClassifyToolRisk:
    """classify_tool_risk 风险分级测试。"""

    def test_approval_required_flag(self) -> None:
        """工具标记 approval_required=True 时始终返回 True。"""
        assert classify_tool_risk("get_info", approval_required=True) is True

    def test_safe_prefix_get(self) -> None:
        assert classify_tool_risk("get_user") is False

    def test_safe_prefix_list(self) -> None:
        assert classify_tool_risk("list_files") is False

    def test_safe_prefix_read(self) -> None:
        assert classify_tool_risk("read_config") is False

    def test_safe_prefix_search(self) -> None:
        assert classify_tool_risk("search_documents") is False

    def test_safe_prefix_query(self) -> None:
        assert classify_tool_risk("query_database") is False

    def test_risky_prefix_delete(self) -> None:
        assert classify_tool_risk("delete_user") is True

    def test_risky_prefix_execute(self) -> None:
        assert classify_tool_risk("execute_command") is True

    def test_risky_prefix_deploy(self) -> None:
        assert classify_tool_risk("deploy_service") is True

    def test_risky_prefix_send(self) -> None:
        assert classify_tool_risk("send_email") is True

    def test_unknown_tool_is_risky(self) -> None:
        """未知工具默认视为高风险。"""
        assert classify_tool_risk("custom_unknown_tool") is True

    def test_case_insensitive(self) -> None:
        """工具名大小写不敏感。"""
        assert classify_tool_risk("GET_USER") is False
        assert classify_tool_risk("Delete_File") is True

    def test_safe_overrides_risky(self) -> None:
        """安全前缀优先于高风险检查（因为先匹配）。"""
        # get_ 是安全前缀，即使名称中包含 delete
        assert classify_tool_risk("get_delete_log") is False


class TestApprovalEnums:

    def test_approval_mode_values(self) -> None:
        assert ApprovalMode.SUGGEST.value == "suggest"
        assert ApprovalMode.AUTO_EDIT.value == "auto-edit"
        assert ApprovalMode.FULL_AUTO.value == "full-auto"

    def test_approval_decision_values(self) -> None:
        assert ApprovalDecision.APPROVED.value == "approved"
        assert ApprovalDecision.REJECTED.value == "rejected"
        assert ApprovalDecision.TIMEOUT.value == "timeout"

    def test_approval_rejected_error(self) -> None:
        err = ApprovalRejectedError("delete_all", "too dangerous")
        assert err.tool_name == "delete_all"
        assert err.reason == "too dangerous"
        assert "delete_all" in str(err)
        assert "rejected" in str(err).lower()
