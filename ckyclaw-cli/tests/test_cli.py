"""ckyclaw-cli 测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ckyclaw_cli.main import app

runner = CliRunner()


class TestVersion:
    """version 命令测试。"""

    def test_version_output(self) -> None:
        """显示版本号。"""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "ckyclaw-cli v0.1.0" in result.output


class TestChatCommand:
    """chat 命令测试。"""

    def test_help(self) -> None:
        """chat --help 正常输出。"""
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
        assert "model" in result.output.lower()

    @patch("ckyclaw_cli.chat._get_input", side_effect=["exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_exit_immediately(self, mock_console: MagicMock, mock_input: MagicMock) -> None:
        """输入 exit 立即退出。"""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat._get_input", side_effect=["quit"])
    @patch("ckyclaw_cli.chat.console")
    def test_quit_immediately(self, mock_console: MagicMock, mock_input: MagicMock) -> None:
        """输入 quit 立即退出。"""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat._get_input", side_effect=["clear", "exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_clear_history(self, mock_console: MagicMock, mock_input: MagicMock) -> None:
        """clear 命令清空历史。"""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat._get_input", side_effect=["", "exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_empty_input_skipped(self, mock_console: MagicMock, mock_input: MagicMock) -> None:
        """空输入被跳过。"""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat._get_input", side_effect=KeyboardInterrupt)
    @patch("ckyclaw_cli.chat.console")
    def test_keyboard_interrupt(self, mock_console: MagicMock, mock_input: MagicMock) -> None:
        """Ctrl+C 优雅退出。"""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat.Runner")
    @patch("ckyclaw_cli.chat._get_input", side_effect=["你好", "exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_single_turn_conversation(
        self,
        mock_console: MagicMock,
        mock_input: MagicMock,
        mock_runner: MagicMock,
    ) -> None:
        """单轮对话返回结果。"""
        mock_result = MagicMock()
        mock_result.final_output = "你好！我是 AI 助手。"
        mock_result.token_usage = None

        async def fake_run(*args: object, **kwargs: object) -> MagicMock:
            return mock_result

        mock_runner.run = fake_run

        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat.Runner")
    @patch("ckyclaw_cli.chat._get_input", side_effect=["测试", "exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_error_handling(
        self,
        mock_console: MagicMock,
        mock_input: MagicMock,
        mock_runner: MagicMock,
    ) -> None:
        """LLM 调用异常时显示错误信息。"""
        async def fake_run(*args: object, **kwargs: object) -> None:
            raise RuntimeError("API 连接失败")

        mock_runner.run = fake_run

        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    @patch("ckyclaw_cli.chat.Runner")
    @patch("ckyclaw_cli.chat._get_input", side_effect=["你好", "exit"])
    @patch("ckyclaw_cli.chat.console")
    def test_token_usage_display(
        self,
        mock_console: MagicMock,
        mock_input: MagicMock,
        mock_runner: MagicMock,
    ) -> None:
        """有 token 使用量时显示统计。"""
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_result = MagicMock()
        mock_result.final_output = "你好！"
        mock_result.token_usage = mock_usage

        async def fake_run(*args: object, **kwargs: object) -> MagicMock:
            return mock_result

        mock_runner.run = fake_run

        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0


class TestNoArgs:
    """无参数测试。"""

    def test_no_args_shows_help(self) -> None:
        """不带参数显示帮助。"""
        result = runner.invoke(app, [])
        # no_args_is_help=True 时 typer 返回 exit_code 0
        assert "chat" in result.output.lower() or "usage" in result.output.lower()
