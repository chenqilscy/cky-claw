"""ApprovalManager — 进程内审批事件管理器。

单例模式，管理 pending 审批的 asyncio.Event，支持 resolve 和超时。
适用于单实例 MVP 部署。多实例场景需升级为 Redis Pub/Sub。
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from ckyclaw_framework.approval.mode import ApprovalDecision

logger = logging.getLogger(__name__)


class ApprovalManager:
    """进程内审批事件管理。"""

    _instance: ApprovalManager | None = None

    def __init__(self) -> None:
        self._pending: dict[uuid.UUID, asyncio.Event] = {}
        self._decisions: dict[uuid.UUID, ApprovalDecision] = {}

    @classmethod
    def get_instance(cls) -> ApprovalManager:
        """获取全局单例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）。"""
        cls._instance = None

    def register(self, approval_id: uuid.UUID) -> None:
        """注册一个 pending 审批事件。"""
        self._pending[approval_id] = asyncio.Event()

    async def wait_for_decision(
        self,
        approval_id: uuid.UUID,
        timeout: int = 300,
    ) -> ApprovalDecision:
        """等待审批结果，超时返回 TIMEOUT。"""
        event = self._pending.get(approval_id)
        if event is None:
            logger.warning("Approval %s not registered, returning TIMEOUT", approval_id)
            return ApprovalDecision.TIMEOUT
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.info("Approval %s timed out after %ds", approval_id, timeout)
            return ApprovalDecision.TIMEOUT
        finally:
            self.cleanup(approval_id)
        return self._decisions.pop(approval_id, ApprovalDecision.TIMEOUT)

    def resolve(self, approval_id: uuid.UUID, decision: ApprovalDecision) -> bool:
        """解决审批请求。返回是否成功（True=有对应 pending）。"""
        event = self._pending.get(approval_id)
        if event is None:
            return False
        self._decisions[approval_id] = decision
        event.set()
        return True

    def cleanup(self, approval_id: uuid.UUID) -> None:
        """清理 pending 事件。"""
        self._pending.pop(approval_id, None)

    @property
    def pending_count(self) -> int:
        """当前 pending 审批数量。"""
        return len(self._pending)
