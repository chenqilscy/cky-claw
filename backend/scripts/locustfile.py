"""Kasaya 性能基准测试脚本 (locust)。

使用方式:
    cd backend
    uv run locust -f scripts/locustfile.py --host=http://localhost:8000

关键 API 延迟基线：
    - GET  /api/v1/health           < 50ms
    - GET  /api/v1/agents           < 200ms
    - GET  /api/v1/traces/stats     < 300ms
    - GET  /api/v1/token-usage      < 200ms
    - GET  /api/v1/agents/realtime-status  < 300ms
"""

from __future__ import annotations

import os

from locust import HttpUser, between, tag, task


class KasayaUser(HttpUser):
    """模拟已认证用户对核心 API 的访问模式。"""

    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        """登录获取 JWT token。"""
        username = os.getenv("LOCUST_USERNAME", "admin")
        password = os.getenv("LOCUST_PASSWORD", "admin123")
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = ""
            self.headers = {}

    # ------- 健康检查 -------

    @tag("health")
    @task(5)
    def health_check(self) -> None:
        """GET /api/v1/health — 期望 < 50ms。"""
        self.client.get("/api/v1/health", name="/health")

    # ------- Agent 管理 -------

    @tag("agents")
    @task(3)
    def list_agents(self) -> None:
        """GET /api/v1/agents — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/agents?limit=20&offset=0",
            headers=self.headers,
            name="/agents [list]",
        )

    @tag("agents")
    @task(2)
    def agent_realtime_status(self) -> None:
        """GET /api/v1/agents/realtime-status — 期望 < 300ms。"""
        self.client.get(
            "/api/v1/agents/realtime-status?minutes=5",
            headers=self.headers,
            name="/agents/realtime-status",
        )

    @tag("agents")
    @task(1)
    def agent_activity_trend(self) -> None:
        """GET /api/v1/agents/activity-trend — 期望 < 300ms。"""
        self.client.get(
            "/api/v1/agents/activity-trend?hours=1&interval=5",
            headers=self.headers,
            name="/agents/activity-trend",
        )

    # ------- Traces -------

    @tag("traces")
    @task(3)
    def trace_stats(self) -> None:
        """GET /api/v1/traces/stats — 期望 < 300ms。"""
        self.client.get(
            "/api/v1/traces/stats",
            headers=self.headers,
            name="/traces/stats",
        )

    @tag("traces")
    @task(2)
    def list_traces(self) -> None:
        """GET /api/v1/traces — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/traces?limit=20&offset=0",
            headers=self.headers,
            name="/traces [list]",
        )

    # ------- Token Usage -------

    @tag("token-usage")
    @task(2)
    def list_token_usage(self) -> None:
        """GET /api/v1/token-usage — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/token-usage?limit=20&offset=0",
            headers=self.headers,
            name="/token-usage [list]",
        )

    @tag("token-usage")
    @task(2)
    def token_usage_summary(self) -> None:
        """GET /api/v1/token-usage/summary — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/token-usage/summary?group_by=model",
            headers=self.headers,
            name="/token-usage/summary",
        )

    @tag("token-usage")
    @task(1)
    def token_usage_trend(self) -> None:
        """GET /api/v1/token-usage/trend — 期望 < 300ms。"""
        self.client.get(
            "/api/v1/token-usage/trend?days=7",
            headers=self.headers,
            name="/token-usage/trend",
        )

    # ------- Sessions -------

    @tag("sessions")
    @task(2)
    def list_sessions(self) -> None:
        """GET /api/v1/sessions — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/sessions?limit=20&offset=0",
            headers=self.headers,
            name="/sessions [list]",
        )

    # ------- Templates -------

    @tag("templates")
    @task(1)
    def list_templates(self) -> None:
        """GET /api/v1/agent-templates — 期望 < 200ms。"""
        self.client.get(
            "/api/v1/agent-templates?limit=50",
            headers=self.headers,
            name="/agent-templates [list]",
        )

    # ------- Dashboard 组合场景 -------

    @tag("dashboard")
    @task(1)
    def dashboard_combo(self) -> None:
        """模拟 Dashboard 页面并发加载 7 个 API。"""
        with self.client.get(
            "/api/v1/agents?limit=1&offset=0",
            headers=self.headers,
            name="/dashboard/agents",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status {resp.status_code}")

        with self.client.get(
            "/api/v1/sessions?limit=1&offset=0",
            headers=self.headers,
            name="/dashboard/sessions",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status {resp.status_code}")

        self.client.get(
            "/api/v1/traces/stats",
            headers=self.headers,
            name="/dashboard/trace-stats",
        )
        self.client.get(
            "/api/v1/token-usage/summary?group_by=model",
            headers=self.headers,
            name="/dashboard/token-summary",
        )
