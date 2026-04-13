"""response_style 模块单元测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.agent.response_style import (
    CONCISE_STYLE_PROMPT,
    RESPONSE_STYLES,
    get_response_style_prompt,
)


class TestResponseStyleConstants:
    """常量和注册表。"""

    def test_concise_style_prompt_non_empty(self) -> None:
        """CONCISE_STYLE_PROMPT 不为空。"""
        assert isinstance(CONCISE_STYLE_PROMPT, str)
        assert len(CONCISE_STYLE_PROMPT) > 100

    def test_response_styles_contains_concise(self) -> None:
        """注册表包含 concise 风格。"""
        assert "concise" in RESPONSE_STYLES
        assert RESPONSE_STYLES["concise"] is CONCISE_STYLE_PROMPT

    def test_concise_style_contains_key_rules(self) -> None:
        """核心规则关键词检查。"""
        # talk-normal 的几条核心规则
        assert "filler" in CONCISE_STYLE_PROMPT.lower() or "废话" in CONCISE_STYLE_PROMPT


class TestGetResponseStylePrompt:
    """get_response_style_prompt 函数。"""

    def test_none_returns_none(self) -> None:
        assert get_response_style_prompt(None) is None

    def test_concise_returns_prompt(self) -> None:
        result = get_response_style_prompt("concise")
        assert result is not None
        assert result == CONCISE_STYLE_PROMPT

    def test_unknown_style_returns_none(self) -> None:
        """未知风格返回 None。"""
        assert get_response_style_prompt("nonexistent") is None

    def test_empty_string_returns_none(self) -> None:
        """空字符串返回 None。"""
        assert get_response_style_prompt("") is None
