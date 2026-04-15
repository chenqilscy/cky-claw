"""ApprovalHandler — 审批处理器抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ckyclaw_framework.approval.mode import ApprovalDecision
    from ckyclaw_framework.runner.run_context import RunContext


class ApprovalHandler(ABC):
    """审批处理器抽象接口。

    CkyClaw 应用层实现此接口，对接 WebSocket 推送 / HTTP API / CLI 等审批通道。
    """

    @abstractmethod
    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,
        action_detail: dict[str, Any],
        timeout: int = 300,
    ) -> ApprovalDecision:
        """发起审批请求，等待结果。

        Args:
            run_context: 当前运行上下文
            action_type: 操作类型 ("tool_call" | "output" | "handoff")
            action_detail: 操作详情（工具名+参数 / 输出内容 / 目标 Agent）
            timeout: 超时秒数

        Returns:
            ApprovalDecision.APPROVED / REJECTED / TIMEOUT
        """
        ...
