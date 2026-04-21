"""Agent 扩展测试 — 覆盖 as_tool model_dump_json 路径 + from_yaml/from_dict。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kasaya.agent.agent import Agent


class TestAgentFromYaml:
    """from_yaml 未实现。"""

    def test_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            Agent.from_yaml("path.yaml")


class TestAgentFromDict:
    """from_dict 未实现。"""

    def test_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            Agent.from_dict({"name": "test"})


class TestAgentAsToolModelDumpJson:
    """as_tool 结构化输出路径 — output 对象有 model_dump_json 方法。"""

    @pytest.mark.asyncio
    async def test_model_dump_json_path(self) -> None:
        """输出对象有 model_dump_json 时，调用它并返回 JSON 字符串。"""
        agent = Agent(name="test_agent", instructions="test")

        # mock Runner.run 返回带 model_dump_json 的输出
        mock_output = MagicMock()
        mock_output.model_dump_json.return_value = '{"key": "value"}'

        mock_result = MagicMock()
        mock_result.output = mock_output

        tool = agent.as_tool()

        with patch("kasaya.runner.runner.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            result = await tool.fn("test input")

        assert result == '{"key": "value"}'
        mock_output.model_dump_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_str_fallback_path(self) -> None:
        """输出对象无 model_dump_json 时，走 str() 路径。"""
        agent = Agent(name="test_agent", instructions="test")

        mock_result = MagicMock()
        mock_result.output = 42  # int, 无 model_dump_json

        tool = agent.as_tool()

        with patch("kasaya.runner.runner.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            result = await tool.fn("test input")

        assert result == "42"

    @pytest.mark.asyncio
    async def test_string_output_path(self) -> None:
        """输出是 str 时直接返回。"""
        agent = Agent(name="test_agent", instructions="test")

        mock_result = MagicMock()
        mock_result.output = "plain text"

        tool = agent.as_tool()

        with patch("kasaya.runner.runner.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            result = await tool.fn("test input")

        assert result == "plain text"
