"""Runner response_style 注入测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.agent import Agent
from ckyclaw_framework.agent.response_style import CONCISE_STYLE_PROMPT
from ckyclaw_framework.runner.runner import RunConfig, RunContext, _build_system_message


def _ctx(agent: Agent) -> RunContext:
    """构造最小 RunContext。"""
    return RunContext(agent=agent, config=RunConfig())


class TestRunnerResponseStyleInjection:
    """_build_system_message 的 response_style 注入。"""

    @pytest.mark.asyncio
    async def test_no_style_unchanged(self) -> None:
        """response_style=None 时 instructions 不变。"""
        agent = Agent(name="a", instructions="Hello world")
        msg = await _build_system_message(agent, _ctx(agent))
        assert msg.content == "Hello world"

    @pytest.mark.asyncio
    async def test_concise_style_prepends(self) -> None:
        """response_style='concise' 在 instructions 前注入 talk-normal 规则。"""
        agent = Agent(name="b", instructions="Be helpful.", response_style="concise")
        msg = await _build_system_message(agent, _ctx(agent))
        assert msg.content.startswith(CONCISE_STYLE_PROMPT)
        assert "Be helpful." in msg.content

    @pytest.mark.asyncio
    async def test_concise_style_empty_instructions(self) -> None:
        """instructions 为空时只有 style prompt。"""
        agent = Agent(name="c", instructions="", response_style="concise")
        msg = await _build_system_message(agent, _ctx(agent))
        assert msg.content == CONCISE_STYLE_PROMPT

    @pytest.mark.asyncio
    async def test_unknown_style_ignored(self) -> None:
        """未注册的 style 不改变 instructions。"""
        agent = Agent(name="d", instructions="Test", response_style="nonexistent")
        msg = await _build_system_message(agent, _ctx(agent))
        assert msg.content == "Test"
