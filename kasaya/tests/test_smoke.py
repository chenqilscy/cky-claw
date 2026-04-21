"""Kasaya Framework 基础冒烟测试。"""

from __future__ import annotations


def test_import() -> None:
    """验证包可以正确 import。"""
    from kasaya.agent.agent import Agent
    from kasaya.model.message import Message, MessageRole
    from kasaya.runner.runner import Runner

    assert Agent is not None
    assert Runner is not None
    assert Message is not None
    assert MessageRole.USER == "user"
