"""API 客户端测试。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from unittest.mock import patch

import pytest

from kasaya_cli.client import KasayaClient


class MockHandler(BaseHTTPRequestHandler):
    """简易 HTTP Mock 服务。"""

    responses: dict[str, tuple[int, Any]] = {}

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        key = f"{self.command} {self.path.split('?')[0]}"
        status, body = self.responses.get(key, (404, {"detail": "not found"}))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format: str, *args: object) -> None:
        pass  # 静默日志


@pytest.fixture()
def mock_server():
    """启动本地 Mock HTTP 服务器。"""
    server = HTTPServer(("127.0.0.1", 0), MockHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", MockHandler
    server.shutdown()


class TestKasayaClient:
    """API 客户端测试。"""

    def test_default_url(self) -> None:
        """默认 URL。"""
        client = KasayaClient()
        assert client.base_url == "http://localhost:8000"

    def test_env_url(self) -> None:
        """从环境变量读取 URL。"""
        with patch.dict("os.environ", {"KASAYA_URL": "http://example.com:9000"}):
            client = KasayaClient()
            assert client.base_url == "http://example.com:9000"

    def test_explicit_url(self) -> None:
        """显式传入 URL。"""
        client = KasayaClient(base_url="http://test:1234/")
        assert client.base_url == "http://test:1234"

    def test_login(self, mock_server: tuple) -> None:
        """登录获取 token。"""
        url, handler = mock_server
        handler.responses = {
            "POST /api/v1/auth/login": (200, {"access_token": "test-jwt-token"}),
        }
        client = KasayaClient(base_url=url)
        token = client.login("admin", "pass")
        assert token == "test-jwt-token"
        assert client.token == "test-jwt-token"

    def test_list_agents(self, mock_server: tuple) -> None:
        """查询 Agent 列表。"""
        url, handler = mock_server
        handler.responses = {
            "GET /api/v1/agents": (200, {
                "data": [{"id": "abc", "name": "test-agent"}],
                "total": 1,
            }),
        }
        client = KasayaClient(base_url=url, token="jwt")
        resp = client.list_agents()
        assert resp["total"] == 1
        assert resp["data"][0]["name"] == "test-agent"

    def test_list_providers(self, mock_server: tuple) -> None:
        """查询 Provider 列表。"""
        url, handler = mock_server
        handler.responses = {
            "GET /api/v1/providers": (200, {
                "data": [{"id": "p1", "name": "deepseek", "provider_type": "deepseek"}],
                "total": 1,
            }),
        }
        client = KasayaClient(base_url=url, token="jwt")
        resp = client.list_providers()
        assert resp["total"] == 1

    def test_test_provider(self, mock_server: tuple) -> None:
        """测试 Provider 连通性。"""
        url, handler = mock_server
        handler.responses = {
            "POST /api/v1/providers/p1/test": (200, {
                "success": True, "latency_ms": 500, "model_used": "deepseek-chat",
            }),
        }
        client = KasayaClient(base_url=url, token="jwt")
        resp = client.test_provider("p1")
        assert resp["success"] is True

    def test_http_error(self, mock_server: tuple) -> None:
        """HTTP 错误处理。"""
        url, handler = mock_server
        handler.responses = {
            "GET /api/v1/agents/bad-id": (404, {"detail": "Agent not found"}),
        }
        client = KasayaClient(base_url=url, token="jwt")
        with pytest.raises(RuntimeError, match="404"):
            client.get_agent("bad-id")

    def test_connection_error(self) -> None:
        """连接失败。"""
        client = KasayaClient(base_url="http://127.0.0.1:1")
        with pytest.raises(RuntimeError, match="连接失败"):
            client.list_agents()
