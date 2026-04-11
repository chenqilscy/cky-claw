"""Provider 子命令测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ckyclaw_cli.main import app

runner = CliRunner()


class TestProviderList:
    """provider list 命令测试。"""

    @patch("ckyclaw_cli.provider_cmd.CkyClawClient")
    def test_list_providers(self, mock_cls: MagicMock) -> None:
        """正常列出 Provider。"""
        mock_client = MagicMock()
        mock_client.list_providers.return_value = {
            "data": [
                {"id": "p1", "name": "deepseek", "provider_type": "deepseek", "is_enabled": True, "base_url": "https://api.deepseek.com"},
            ],
            "total": 1,
        }
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["provider", "list"])
        assert result.exit_code == 0
        assert "deepseek" in result.output

    @patch("ckyclaw_cli.provider_cmd.CkyClawClient")
    def test_list_providers_empty(self, mock_cls: MagicMock) -> None:
        """空列表。"""
        mock_client = MagicMock()
        mock_client.list_providers.return_value = {"data": [], "total": 0}
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["provider", "list"])
        assert result.exit_code == 0
        assert "暂无" in result.output


class TestProviderTest:
    """provider test 命令测试。"""

    @patch("ckyclaw_cli.provider_cmd.CkyClawClient")
    def test_provider_success(self, mock_cls: MagicMock) -> None:
        """连通性测试成功。"""
        mock_client = MagicMock()
        mock_client.test_provider.return_value = {
            "success": True, "latency_ms": 500, "model_used": "deepseek-chat",
        }
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["provider", "test", "p1"])
        assert result.exit_code == 0
        assert "通过" in result.output

    @patch("ckyclaw_cli.provider_cmd.CkyClawClient")
    def test_provider_failure(self, mock_cls: MagicMock) -> None:
        """连通性测试失败。"""
        mock_client = MagicMock()
        mock_client.test_provider.return_value = {
            "success": False, "latency_ms": 0, "error": "API key invalid",
        }
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["provider", "test", "p1"])
        assert result.exit_code == 1
        assert "失败" in result.output

    @patch("ckyclaw_cli.provider_cmd.CkyClawClient")
    def test_provider_api_error(self, mock_cls: MagicMock) -> None:
        """API 错误。"""
        mock_client = MagicMock()
        mock_client.test_provider.side_effect = RuntimeError("HTTP 404: Not found")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, ["provider", "test", "bad-id"])
        assert result.exit_code == 1
