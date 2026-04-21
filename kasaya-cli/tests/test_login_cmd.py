"""登录命令测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kasaya_cli.main import app

runner = CliRunner()


class TestLogin:
    """login 命令测试。"""

    @patch("kasaya_cli.login_cmd.KasayaClient")
    def test_login_success(self, mock_cls: MagicMock) -> None:
        """登录成功显示 token。"""
        mock_client = MagicMock()
        mock_client.login.return_value = "jwt-token-12345"
        mock_client.base_url = "http://localhost:8000"
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["login", "--username", "admin", "--password", "pass123"])
        assert result.exit_code == 0
        assert "成功" in result.output
        assert "KASAYA_TOKEN" in result.output

    @patch("kasaya_cli.login_cmd.KasayaClient")
    def test_login_failure(self, mock_cls: MagicMock) -> None:
        """登录失败显示错误。"""
        mock_client = MagicMock()
        mock_client.login.side_effect = RuntimeError("HTTP 401: Invalid credentials")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["login", "--username", "bad", "--password", "wrong"])
        assert result.exit_code == 1
        assert "失败" in result.output
