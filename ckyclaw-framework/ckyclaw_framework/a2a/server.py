"""A2A Server — 接收并处理外部 Agent 请求。

A2AServer 提供 A2A 协议的服务端实现，负责：
1. 发布 Agent Card（/.well-known/agent.json）
2. 接收 tasks/send 请求并分发到本地 Agent
3. 管理 Task 生命周期
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from ckyclaw_framework.a2a.adapter import A2AAdapter
from ckyclaw_framework.a2a.task import A2ATask, TaskStatus

if TYPE_CHECKING:
    from ckyclaw_framework.a2a.agent_card import AgentCard

logger = logging.getLogger(__name__)

# 任务处理器类型：接收 A2ATask，返回结果文本
TaskHandler = Callable[[A2ATask], Awaitable[str]]


class A2AServer:
    """A2A 服务端 — 接收外部 Agent 请求并路由到本地 Agent。

    使用示例::

        server = A2AServer(card=agent_card)

        # 注册处理器
        async def handle(task: A2ATask) -> str:
            return "处理结果"
        server.register_handler(handle)

        # 处理 JSON-RPC 请求
        response = await server.handle_request(request_body)
    """

    def __init__(self, card: AgentCard) -> None:
        """初始化 A2A Server。

        Args:
            card: 本 Agent 的 Agent Card。
        """
        self._card = card
        self._handler: TaskHandler | None = None
        self._tasks: dict[str, A2ATask] = {}
        self._adapter = A2AAdapter()

    @property
    def card(self) -> AgentCard:
        """获取 Agent Card。"""
        return self._card

    def register_handler(self, handler: TaskHandler) -> None:
        """注册任务处理器。

        Args:
            handler: 异步函数，接收 A2ATask 返回结果文本。
        """
        self._handler = handler

    def get_agent_card(self) -> dict[str, Any]:
        """获取 Agent Card 字典（用于 /.well-known/agent.json）。"""
        return self._card.to_dict()

    async def handle_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """处理 A2A JSON-RPC 请求。

        支持的方法:
        - ``tasks/send``: 发送任务
        - ``tasks/get``: 查询任务状态
        - ``tasks/cancel``: 取消任务

        Args:
            body: JSON-RPC 请求体。

        Returns:
            JSON-RPC 响应体。
        """
        method = body.get("method", "")
        request_id = body.get("id", "")
        params = body.get("params", {})

        if method == "tasks/send":
            return await self._handle_send(request_id, params)
        elif method == "tasks/get":
            return self._handle_get(request_id, params)
        elif method == "tasks/cancel":
            return self._handle_cancel(request_id, params)
        else:
            return self._error_response(request_id, -32601, f"方法不支持: {method}")

    async def _handle_send(self, request_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """处理 tasks/send 请求。"""
        if self._handler is None:
            return self._error_response(request_id, -32603, "未注册任务处理器")

        task = A2ATask(
            id=params.get("id", ""),
            input_messages=params.get("inputMessages", []),
            metadata=params.get("metadata", {}),
        )
        self._tasks[task.id] = task

        try:
            task.transition(TaskStatus.WORKING, "开始处理")
            result_text = await self._handler(task)
            self._adapter.apply_result_to_task(task, result_text=result_text)
        except Exception as e:
            logger.exception("A2A 任务处理失败: %s", e)
            self._adapter.mark_failed(task, error=str(e))

        return self._success_response(request_id, task.to_dict())

    def _handle_get(self, request_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """处理 tasks/get 请求。"""
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if task is None:
            return self._error_response(request_id, -32602, f"任务不存在: {task_id}")
        return self._success_response(request_id, task.to_dict())

    def _handle_cancel(self, request_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """处理 tasks/cancel 请求。"""
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if task is None:
            return self._error_response(request_id, -32602, f"任务不存在: {task_id}")
        try:
            task.transition(TaskStatus.CANCELED, "用户取消")
        except ValueError as e:
            return self._error_response(request_id, -32603, str(e))
        return self._success_response(request_id, task.to_dict())

    def _success_response(self, request_id: str, result: Any) -> dict[str, Any]:
        """构造 JSON-RPC 成功响应。"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _error_response(self, request_id: str, code: int, message: str) -> dict[str, Any]:
        """构造 JSON-RPC 错误响应。"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
