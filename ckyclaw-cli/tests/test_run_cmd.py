"""run 子命令单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ckyclaw_cli.main import app

runner = CliRunner()


class TestRunCommand:
    """run 命令测试集。"""

    def test_run_no_token(self) -> None:
        """未登录时返回错误。"""
        with patch("ckyclaw_cli.run_cmd.CkyClawClient") as mock_cls:
            mock_cls.return_value.token = ""
            result = runner.invoke(app, ["run", "agent-id", "hello"])
        assert result.exit_code == 1
        assert "未登录" in result.output

    def test_run_success(self) -> None:
        """成功运行 Agent 并显示回复。"""
        with patch("ckyclaw_cli.run_cmd.CkyClawClient") as mock_cls:
            client = mock_cls.return_value
            client.token = "test-token"
            client.run_agent.return_value = {"output": "这是 Agent 的回复"}
            result = runner.invoke(app, ["run", "agent-id", "你好"])
        assert result.exit_code == 0
        assert "Agent 的回复" in result.output

    def test_run_with_usage(self) -> None:
        """显示 token 用量。"""
        with patch("ckyclaw_cli.run_cmd.CkyClawClient") as mock_cls:
            client = mock_cls.return_value
            client.token = "test-token"
            client.run_agent.return_value = {
                "output": "回复",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
            result = runner.invoke(app, ["run", "agent-id", "测试"])
        assert result.exit_code == 0
        assert "150" in result.output

    def test_run_from_messages(self) -> None:
        """从 messages 数组提取回复。"""
        with patch("ckyclaw_cli.run_cmd.CkyClawClient") as mock_cls:
            client = mock_cls.return_value
            client.token = "test-token"
            client.run_agent.return_value = {
                "messages": [
                    {"role": "user", "content": "问题"},
                    {"role": "assistant", "content": "从消息提取的回复"},
                ]
            }
            result = runner.invoke(app, ["run", "agent-id", "问"])
        assert result.exit_code == 0
        assert "从消息提取的回复" in result.output

    def test_run_api_error(self) -> None:
        """API 错误时优雅退出。"""
        with patch("ckyclaw_cli.run_cmd.CkyClawClient") as mock_cls:
            client = mock_cls.return_value
            client.token = "test-token"
            client.run_agent.side_effect = RuntimeError("HTTP 500: Internal Error")
            result = runner.invoke(app, ["run", "agent-id", "hello"])
        assert result.exit_code == 1
        assert "运行失败" in result.output
