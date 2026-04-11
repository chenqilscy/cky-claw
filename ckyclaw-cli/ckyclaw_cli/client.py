"""CkyClaw Backend API 客户端。"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CkyClawClient:
    """轻量级 HTTP 客户端，封装 CkyClaw Backend REST API。"""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("CKYCLAW_URL", "http://localhost:8000")).rstrip("/")
        self.token = token or os.environ.get("CKYCLAW_TOKEN", "")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """发送 HTTP 请求，返回 JSON 响应。"""
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            try:
                detail = json.loads(error_body).get("detail", error_body)
            except (json.JSONDecodeError, AttributeError):
                detail = error_body
            raise RuntimeError(f"HTTP {e.code}: {detail}") from e
        except URLError as e:
            raise RuntimeError(f"连接失败: {e.reason}") from e

    def login(self, username: str, password: str) -> str:
        """登录获取 JWT token。"""
        resp = self._request("POST", "/api/v1/auth/login", {"username": username, "password": password})
        self.token = resp["access_token"]
        return self.token

    # ── Agent ─────────────────────────────────────

    def list_agents(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """查询 Agent 列表。"""
        return self._request("GET", f"/api/v1/agents?limit={limit}&offset={offset}")

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """获取单个 Agent 详情。"""
        return self._request("GET", f"/api/v1/agents/{agent_id}")

    # ── Provider ──────────────────────────────────

    def list_providers(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """查询 Provider 列表。"""
        return self._request("GET", f"/api/v1/providers?limit={limit}&offset={offset}")

    def test_provider(self, provider_id: str) -> dict[str, Any]:
        """测试 Provider 连通性。"""
        return self._request("POST", f"/api/v1/providers/{provider_id}/test")

    # ── Run ───────────────────────────────────────

    def run_agent(self, agent_id: str, message: str) -> dict[str, Any]:
        """创建 Session 并运行 Agent（同步模式）。"""
        # 1. 创建 Session
        session = self._request("POST", "/api/v1/sessions", {
            "agent_id": agent_id,
            "title": f"CLI run: {message[:40]}",
        })
        session_id = session["id"]

        # 2. 运行
        return self._request("POST", f"/api/v1/sessions/{session_id}/run", {
            "message": message,
            "config": {"stream": False},
        })
