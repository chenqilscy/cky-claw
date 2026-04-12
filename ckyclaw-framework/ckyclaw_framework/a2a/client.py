"""A2A Client — 调用外部 A2A Agent。

A2AClient 封装对远程 A2A Agent 的发现和任务发送逻辑。
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urljoin

from ckyclaw_framework.a2a.agent_card import AgentCard
from ckyclaw_framework.a2a.task import A2ATask, TaskStatus

logger = logging.getLogger(__name__)


class A2AClientError(Exception):
    """A2A 客户端错误。"""


class A2AClient:
    """A2A 客户端 — 发现并调用远程 A2A Agent。

    使用示例::

        client = A2AClient()

        # 发现远程 Agent
        card = await client.discover("https://remote-agent.example.com")

        # 发送任务
        task = A2ATask(
            input_messages=[{"role": "user", "parts": [{"type": "text/plain", "text": "hello"}]}]
        )
        result = await client.send_task(card, task)
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        """初始化客户端。

        Args:
            timeout: HTTP 请求超时（秒）。
            headers: 全局请求头（如 Authorization）。
        """
        self._timeout = timeout
        self._headers = headers or {}

    async def discover(self, base_url: str) -> AgentCard:
        """通过 /.well-known/agent.json 发现远程 Agent。

        Args:
            base_url: 远程 Agent 的基础 URL。

        Returns:
            AgentCard 实例。

        Raises:
            A2AClientError: 发现失败。
        """
        try:
            import httpx
        except ImportError as e:
            raise A2AClientError("需要安装 httpx: pip install httpx") from e

        well_known_url = urljoin(base_url.rstrip("/") + "/", ".well-known/agent.json")
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as http:
                resp = await http.get(well_known_url)
                resp.raise_for_status()
                data = resp.json()
                return AgentCard.from_dict(data)
        except httpx.HTTPStatusError as e:
            raise A2AClientError(f"Agent Card 请求失败: HTTP {e.response.status_code}") from e
        except Exception as e:
            raise A2AClientError(f"发现 Agent 失败: {e}") from e

    async def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """向远程 Agent 发送任务。

        Args:
            card: 目标 Agent Card。
            task: 要发送的任务。

        Returns:
            远程 Agent 返回的任务（含结果）。

        Raises:
            A2AClientError: 请求失败。
        """
        try:
            import httpx
        except ImportError as e:
            raise A2AClientError("需要安装 httpx: pip install httpx") from e

        url = card.url
        if not url:
            raise A2AClientError("Agent Card 未指定 url")

        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": task.id,
            "params": task.to_dict(),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise A2AClientError(f"远程 Agent 返回错误: {body['error']}")
                result_data = body.get("result", body)
                return A2ATask.from_dict(result_data)
        except A2AClientError:
            raise
        except Exception as e:
            raise A2AClientError(f"发送任务失败: {e}") from e

    async def get_task(self, card: AgentCard, task_id: str) -> A2ATask:
        """查询远程任务状态。

        Args:
            card: 目标 Agent Card。
            task_id: 任务 ID。

        Returns:
            任务当前状态。

        Raises:
            A2AClientError: 请求失败。
        """
        try:
            import httpx
        except ImportError as e:
            raise A2AClientError("需要安装 httpx: pip install httpx") from e

        url = card.url
        if not url:
            raise A2AClientError("Agent Card 未指定 url")

        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "id": task_id,
            "params": {"id": task_id},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise A2AClientError(f"远程 Agent 返回错误: {body['error']}")
                result_data = body.get("result", body)
                return A2ATask.from_dict(result_data)
        except A2AClientError:
            raise
        except Exception as e:
            raise A2AClientError(f"查询任务失败: {e}") from e

    async def cancel_task(self, card: AgentCard, task_id: str) -> A2ATask:
        """取消远程任务。

        Args:
            card: 目标 Agent Card。
            task_id: 任务 ID。

        Returns:
            取消后的任务状态。

        Raises:
            A2AClientError: 请求失败。
        """
        try:
            import httpx
        except ImportError as e:
            raise A2AClientError("需要安装 httpx: pip install httpx") from e

        url = card.url
        if not url:
            raise A2AClientError("Agent Card 未指定 url")

        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "id": task_id,
            "params": {"id": task_id},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise A2AClientError(f"远程 Agent 返回错误: {body['error']}")
                result_data = body.get("result", body)
                return A2ATask.from_dict(result_data)
        except A2AClientError:
            raise
        except Exception as e:
            raise A2AClientError(f"取消任务失败: {e}") from e
