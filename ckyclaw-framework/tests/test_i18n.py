"""Agent 国际化 LocalizedInstructions 单元测试。"""

from __future__ import annotations

from ckyclaw_framework.agent.i18n import LocalizedInstructions


class TestLocalizedInstructions:
    """LocalizedInstructions 解析测试。"""

    def test_exact_match(self) -> None:
        """精确匹配 locale。"""
        li = LocalizedInstructions(
            default_locale="zh-CN",
            instructions={"zh-CN": "中文指令", "en-US": "English instructions"},
        )
        assert li.resolve("en-US") == "English instructions"
        assert li.resolve("zh-CN") == "中文指令"

    def test_language_fallback(self) -> None:
        """语言级匹配：zh-TW 匹配到 zh-CN。"""
        li = LocalizedInstructions(
            default_locale="zh-CN",
            instructions={"zh-CN": "中文指令", "en-US": "English"},
        )
        assert li.resolve("zh-TW") == "中文指令"

    def test_language_fallback_en(self) -> None:
        """语言级匹配：en-GB 匹配到 en-US。"""
        li = LocalizedInstructions(
            default_locale="zh-CN",
            instructions={"zh-CN": "中文", "en-US": "English"},
        )
        assert li.resolve("en-GB") == "English"

    def test_default_fallback(self) -> None:
        """无匹配时回退到默认语言。"""
        li = LocalizedInstructions(
            default_locale="zh-CN",
            instructions={"zh-CN": "中文指令"},
        )
        assert li.resolve("ja-JP") == "中文指令"

    def test_empty_instructions(self) -> None:
        """空 instructions 返回空字符串。"""
        li = LocalizedInstructions(default_locale="zh-CN", instructions={})
        assert li.resolve("en-US") == ""

    def test_bare_language_code(self) -> None:
        """纯语言码（不带地区）精确匹配。"""
        li = LocalizedInstructions(
            default_locale="en",
            instructions={"en": "English", "zh": "中文"},
        )
        assert li.resolve("en") == "English"
        assert li.resolve("zh") == "中文"

    def test_bare_language_matches_regional(self) -> None:
        """纯语言码 'zh' 可匹配到 'zh-CN'。"""
        li = LocalizedInstructions(
            default_locale="zh-CN",
            instructions={"zh-CN": "中文指令"},
        )
        # 'zh' 不精确匹配 'zh-CN'，但语言前缀 'zh' 匹配 'zh-CN'
        assert li.resolve("zh") == "中文指令"
