"""Agent 子命令测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kasaya_cli.main import app

runner = CliRunner()


class TestAgentList:
    """agent list 命令测试。"""

    @patch("kasaya_cli.agent_cmd.KasayaClient")
    def test_list_agents(self, mock_cls: MagicMock) -> None:
        """正常列出 Agent。"""
        mock_client = MagicMock()
        mock_client.list_agents.return_value = {
            "data": [
                {"id": "aaa-111", "name": "code-reviewer", "model": "gpt-4o", "is_active": True, "created_at": "2026-01-01T00:00:00"},
            ],
            "total": 1,
        }
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0
        assert "code-reviewer" in result.output

    @patch("kasaya_cli.agent_cmd.KasayaClient")
    def test_list_agents_empty(self, mock_cls: MagicMock) -> None:
        """空 Agent 列表。"""
        mock_client = MagicMock()
        mock_client.list_agents.return_value = {"data": [], "total": 0}
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0
        assert "暂无" in result.output

    @patch("kasaya_cli.agent_cmd.KasayaClient")
    def test_list_agents_error(self, mock_cls: MagicMock) -> None:
        """API 错误。"""
        mock_client = MagicMock()
        mock_client.list_agents.side_effect = RuntimeError("HTTP 401: Unauthorized")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 1
        assert "错误" in result.output


class TestAgentGet:
    """agent get 命令测试。"""

    @patch("kasaya_cli.agent_cmd.KasayaClient")
    def test_get_agent(self, mock_cls: MagicMock) -> None:
        """查看 Agent 详情。"""
        mock_client = MagicMock()
        mock_client.get_agent.return_value = {
            "id": "aaa-111",
            "name": "code-reviewer",
            "model": "gpt-4o",
            "instructions": "Review code carefully",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        }
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["agent", "get", "aaa-111"])
        assert result.exit_code == 0
        assert "code-reviewer" in result.output

    @patch("kasaya_cli.agent_cmd.KasayaClient")
    def test_get_agent_not_found(self, mock_cls: MagicMock) -> None:
        """Agent 不存在。"""
        mock_client = MagicMock()
        mock_client.get_agent.side_effect = RuntimeError("HTTP 404: Agent not found")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["agent", "get", "bad-id"])
        assert result.exit_code == 1
